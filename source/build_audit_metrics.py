"""감사보고서 본표를 추출·검산하고 출처를 남긴다. 불명확한 표는 반영하지 않는다."""
from __future__ import annotations  # 파이썬 3.9에서도 X | None 표기 허용
from pathlib import Path
import re,zipfile,sys,json,math
from lxml import etree
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/processed'

def norm(s):
    return re.sub(r'[\s\u3000]','',s)

def label(s):
    s=re.sub(r'\((?:주석|주)[0-9,~\-]+\)','',norm(s))
    return re.sub(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVX0-9.．()\-]+','',s)

def amount(s):
    s=norm(s).replace(',','').replace('△','-').replace('\u2212','-')
    if s in ('-','\u2013','\u2014'):return 0
    if re.fullmatch(r'\(\d+(?:\.\d+)?\)',s):return -float(s[1:-1])
    if re.fullmatch(r'-?\d+(?:\.\d+)?',s):return float(s)
    return None

def tables_from_document(raw):
    parser=etree.XMLParser(resolve_entities=False,no_network=True,recover=True)
    raw=re.sub(rb'&(?!amp;|lt;|gt;|apos;|quot;|#[0-9]+;|#x[0-9a-fA-F]+;)',b'&amp;',raw)
    root=etree.fromstring(raw,parser)
    leaves=list(root.iter());positions={e:i for i,e in enumerate(leaves)}
    for index,table in enumerate(root.iter('TABLE')):
        rows=[]
        for tr in table.iter('TR'):
            if next(tr.iterancestors('TABLE'),None) is not table:continue
            cells=[c for c in tr if c.tag in ('TD','TH','TE') and not c.findall('.//TABLE')]
            rows.append([''.join(c.itertext()).strip() for c in cells])
        # 표 직전의 단위·날짜 문맥을 사용한다. 원문 자체는 수정하지 않는다.
        earlier=leaves[:positions[table]]
        text=' '.join(''.join(e.itertext()) for e in earlier[-100:] if len(e)==0)
        units=re.findall(r'단위\s*[:：]\s*(백만\s*원|천\s*원|원)',text)
        units=[norm(u) for u in units]
        unit={'원':1,'천원':1000,'백만원':1000000}.get(units[-1]) if units else None
        yield {'index':index,'rows':rows,'context':text[-2500:],'unit':unit}

CORE={'assets':{'자산총계'},'liabilities':{'부채총계'},'equity':{'자본총계'},'revenue':{'매출액','매출','수익(매출액)','영업수익'},'op_income':{'영업이익','영업손실','영업이익(손실)','영업손익'},'net_income':{'당기순이익','당기순손실','당기순손익','당기순이익(손실)','당기순손실(이익)'}}
BORROW={'차입금','단기차입금','장기차입금','유동성장기차입금','유동성장기부채','유동성차입금','사채','유동성사채','차입금및사채','차입금과사채','장단기차입금','단기차입금및유동성장기차입금','사채및장기차입금'}

def pairs(table):
    rows=table['rows'];header=' '.join(' '.join(r) for r in rows[:3])
    terms=re.findall(r'제\s*(\d+)\s*기',header)
    adjacent=len(terms)>=2 and int(terms[0])==int(terms[1])+1
    if not (('당' in header and '전' in header) or re.search(r'20\d{2}',header) or adjacent):return []
    skip=2 if '주석' in norm(header) else 1
    result=[]
    for ri,row in enumerate(rows):
        if len(row)<3:continue
        vals=[(x,amount(x)) for x in row[skip:] if norm(x)]
        if len(vals)!=2 or any(v is None for _,v in vals):continue
        result.append((ri,label(row[0]),row[0],vals))
    return result

def extract(report):
    if report['report_kind']=='A002':
        from extract_half_xml import extract_half
        return extract_half(report)
    z=zipfile.ZipFile(ROOT/str(report['document_path']).replace('\\','/'))
    match=re.search(r'\((20\d{2})\.(\d{2})\)',report['report_nm'])
    if not match:return [],[], '보고서 결산기간 해석 불가'
    year,month=map(int,match.groups());period=str(year) if month==12 else f'{year}FY{month:02}'
    basis='CFS' if report['report_kind']=='F002' else 'OFS'
    found={};trace=[];bs=None;income=None;interest=None
    members=sorted(z.namelist(),key=lambda m:0 if report['report_kind']=='A001' and '_00761.xml' in m else 1)
    for member in members:
        if not member.lower().endswith('.xml'):continue
        try:tables=list(tables_from_document(z.read(member)))
        except etree.XMLSyntaxError:continue
        for t in tables:
            ps=pairs(t); names={p[1] for p in ps}
            if bs is None and {'자산총계','부채총계','자본총계'}<=names:bs=(member,t,ps)
            if income is None and any(names&CORE[k] for k in ['revenue']) and names&CORE['op_income'] and names&CORE['net_income']:income=(member,t,ps)
            if interest is None and '이자비용' in names and '금융비용' in norm(''.join(''.join(r) for r in t['rows'])):interest=(member,t,ps)
    if bs is None or income is None:return [],[], '본표 또는 당기·전기 열 구조 확인 필요'
    if report['report_kind']=='A001':
        basis='CFS' if '연결재무상태표' in norm(bs[1]['context']) else 'OFS'
    for member,t,ps in [bs,income]:
        if not t['unit']:return [],[], '본표 금액 단위 확인 필요'
        for key,aliases in CORE.items():
            hits=[p for p in ps if p[1] in aliases]
            if len(hits)==1:
                ri,nm,rawlabel,vals=hits[0];found[key]=[int(round(v*t['unit'])) for _,v in vals]
                trace.append({'field':key,'table_index':t['index'],'row_index':ri,'row_label':rawlabel,'current_token':vals[0][0],'prior_token':vals[1][0],'unit_multiplier':t['unit'],'xml_member':member})
    proxy=False
    if not interest:
        member,t,ps=income
        costs=[p for p in ps if p[1] in {'금융비용','금융원가'}]
        if len(costs)==1:
            ri,nm,rawlabel,vals=costs[0];found['interest_expense']=[abs(int(round(v*t['unit']))) for _,v in vals];proxy=True
            trace.append({'field':'finance_costs_proxy','table_index':t['index'],'row_index':ri,'row_label':rawlabel,'current_token':vals[0][0],'prior_token':vals[1][0],'unit_multiplier':t['unit'],'xml_member':member})
    if any(k not in found for k in CORE):return [],[], '핵심 계정 중복 또는 누락'
    for offset in range(2):
        diff=found['assets'][offset]-found['liabilities'][offset]-found['equity'][offset]
        if abs(diff)>bs[1]['unit']:return [],[], '자산·부채·자본 검산 실패'
    member,t,ps=bs
    borrowrows=[p for p in ps if p[1] in BORROW]
    unknown=[p[1] for p in ps if re.search('차입|사채',p[1]) and p[1] not in BORROW and not re.search('대여|자산',p[1])]
    generic=[p for p in ps if p[3][0][1] and '금융부채' in p[1] and not re.search('매입|미지급|리스|파생',p[1])]
    if borrowrows and not unknown and not generic:
        found['borrowings']=[sum(int(round(p[3][i][1]*t['unit'])) for p in borrowrows) for i in range(2)]
        for ri,nm,rawlabel,vals in borrowrows:trace.append({'field':'borrowings_component','table_index':t['index'],'row_index':ri,'row_label':rawlabel,'current_token':vals[0][0],'prior_token':vals[1][0],'unit_multiplier':t['unit'],'xml_member':member})
    if interest and interest[1]['unit']:
        member,t,ps=interest;hit=[p for p in ps if p[1]=='이자비용']
        if len(hit)==1:
            ri,nm,rawlabel,vals=hit[0];found['interest_expense']=[int(round(v*t['unit'])) for _,v in vals]
            trace.append({'field':'interest_expense','table_index':t['index'],'row_index':ri,'row_label':rawlabel,'current_token':vals[0][0],'prior_token':vals[1][0],'unit_multiplier':t['unit'],'xml_member':member})
    out=[]
    for i in range(2):
        p=str(year-i) if month==12 else f'{year-i}FY{month:02}'
        r={'corp_name':report['corp_name'],'stock_code':report['stock_code'],'period':p,'period_type':'FY','fs_div':basis,'annualized':False,'icr_basis':'금융원가' if proxy else '이자비용','roe_basis':'순이익/평균자본' if basis=='OFS' else '지배주주 계정 추가 확인 필요',
           'data_source':'AUDIT_XML','fiscal_end':f'{year-i}-{month:02}','source_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+report['rcept_no'],'rcept_no':report['rcept_no'],'balance_tolerance':bs[1]['unit']}
        r.update({k:v[i] for k,v in found.items()})
        def ratio(a,b):return round(a/b*100,2) if b and b>0 else float('nan')
        r['op_margin']=ratio(r['op_income'],r['revenue']);r['debt_ratio']=ratio(r['liabilities'],r['equity'])
        r['borrow_dep']=ratio(r.get('borrowings',float('nan')),r['assets'])
        r['icr']=round(r['op_income']/r['interest_expense'],2) if r.get('interest_expense',0)>0 else float('nan')
        if i==0:
            r['sales_growth']=round((found['revenue'][0]/found['revenue'][1]-1)*100,2) if found['revenue'][1]>0 else float('nan')
            r['roa']=ratio(r['net_income'],sum(found['assets'])/2)
            if basis=='OFS' and min(found['equity'])>0:r['roe']=ratio(r['net_income'],sum(found['equity'])/2)
        out.append(r)
    for t in trace:t.update(corp_name=report['corp_name'],stock_code=report['stock_code'],period=period,rcept_no=report['rcept_no'],source_url=out[0]['source_url'])
    return out,trace,'본표·단위·자산 등식 검산 통과'

def main():
    index=DATA/'audit_report_index.csv'
    if not index.exists():return
    reports=pd.read_csv(index,dtype=str).fillna('');records=[];traces=[];status=[]
    from company_targets import registry
    identifiers={c['corp_code']:c['stock_code'] for c in registry()}
    reports['stock_code']=reports.corp_code.map(identifiers).fillna(reports.stock_code)
    reports.to_csv(index,index=False,encoding='utf-8-sig')
    # 최신 공시 당기 값을 우선. 연결 감사보고서가 있으면 별도와 섞지 않는다.
    reports=reports.sort_values('rcept_no',ascending=False)
    reports['document_path']=reports.document_path.str.replace('\\','/',regex=False)   # Windows 경로 구분자 통일
    cached=DATA/'audit_metrics.csv'
    sources_ok=all((ROOT/p).exists() for p in reports.document_path if p)
    if not sources_ok and cached.exists():
        # 감사보고서 원문 zip(data/raw/audit)이 없으면(용량 때문에 공유본에서 제외) 이전에 추출한 결과를 그대로 사용
        print('감사보고서 원문 없음 → 기존 audit_metrics.csv 재사용')
        audits=pd.read_csv(cached,dtype={'stock_code':str,'period':str})
        traces=pd.read_csv(DATA/'audit_account_mapping.csv',dtype=str).to_dict('records') if (DATA/'audit_account_mapping.csv').exists() else []
    else:
        for _,report in reports.iterrows():
            r,t,note=extract(report);records+=r;traces+=t;status.append({'corp_name':report.corp_name,'rcept_no':report.rcept_no,'status':note})
        pd.DataFrame(status).to_csv(DATA/'audit_extraction_status.csv',index=False,encoding='utf-8-sig')
        if not records:return
        audits=pd.DataFrame(records)
    audits['_basis_order']=audits.fs_div.map({'CFS':0,'OFS':1})
    audits=audits.sort_values(['_basis_order','rcept_no'],ascending=[True,False]).drop_duplicates(['stock_code','period']).drop(columns='_basis_order')
    # 동일 결산월·재무제표 기준의 전기 값으로 성장률과 평균잔액을 계산한다.
    for i,r in audits.iterrows():
        if r.period_type!='FY':continue
        prev=str(int(r.period[:4])-1)+r.period[4:]
        p=audits[(audits.stock_code==r.stock_code)&(audits.period==prev)&(audits.fs_div==r.fs_div)]
        if not p.empty:
            pr=p.iloc[0]
            if pr.revenue>0:audits.loc[i,'sales_growth']=round((r.revenue/pr.revenue-1)*100,2)
            audits.loc[i,'roa']=round(r.net_income/((r.assets+pr.assets)/2)*100,2)
            if r.fs_div=='OFS' and min(r.equity,pr.equity)>0:audits.loc[i,'roe']=round(r.net_income/((r.equity+pr.equity)/2)*100,2)
    audits.to_csv(DATA/'audit_metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(traces).to_csv(DATA/'audit_account_mapping.csv',index=False,encoding='utf-8-sig')
    existing=pd.read_csv(DATA/'metrics.csv',dtype={'stock_code':str,'period':str})
    if 'data_source' in existing:existing=existing[existing.data_source!='AUDIT_XML']
    existing['data_source']='DART_FINANCIAL_API'
    existing['balance_tolerance']=1
    keys=set(zip(existing.stock_code,existing.period))
    audits=audits[[k not in keys for k in zip(audits.stock_code,audits.period)]]
    pd.concat([existing,audits],ignore_index=True).to_csv(DATA/'metrics.csv',index=False,encoding='utf-8-sig')
    quality=pd.read_csv(DATA/'data_quality.csv',dtype={'stock_code':str,'period':str})
    quality=quality[[k in keys for k in zip(quality.stock_code,quality.period)]]
    qr=[]
    for _,r in audits.iterrows():
        missing=[c for c in ['borrowings','interest_expense','icr','borrow_dep'] if pd.isna(r.get(c))]
        ready=not missing and r.equity>0 and r.get('interest_expense',0)>0
        qr.append({'corp_name':r.corp_name,'stock_code':r.stock_code,'period':r.period,'fs_div':r.fs_div,'management_ready':'Y' if ready else 'N','borrowing_mapping':'완료' if pd.notna(r.get('borrowings')) else '확인 필요','icr_basis':r.icr_basis,'status':'공시 원문 본표·단위 검산 통과' if ready else '공시 원문 핵심 재무 확인 · 관리 판정 계정 추가 확인: '+','.join(missing),'source_url':r.source_url})
    pd.concat([quality,pd.DataFrame(qr)],ignore_index=True).to_csv(DATA/'data_quality.csv',index=False,encoding='utf-8-sig')
    print('감사보고서 반영',audits.corp_name.nunique(),'기업',len(audits),'행')

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
