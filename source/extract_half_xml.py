"""반기 XML: 손익의 누적 열과 기말 재무상태를 구분한다."""
import re,zipfile
from build_audit_metrics import ROOT,CORE,BORROW,pairs,tables_from_document,norm,label,amount

def extract_half(report):
    match=re.search(r'\((20\d{2})\.06\)',report['report_nm'])
    if not match:return [],[],'반기 보고기간 확인 필요'
    year=int(match[1]);z=zipfile.ZipFile(ROOT/str(report['document_path']).replace('\\','/'))
    bs=None;income=None
    for member in z.namelist():
        if not member.endswith('.xml'):continue
        for t in tables_from_document(z.read(member)):
            ps=pairs(t);names={p[1] for p in ps}
            if bs is None and {'자산총계','부채총계','자본총계'}<=names and '반기말' in norm(''.join(t['rows'][0])):bs=(member,t,ps)
            header=norm(''.join(''.join(r) for r in t['rows'][:3]))
            if bs and income is None and '3개월누적3개월누적' in header:
                cum=[]
                for ri,row in enumerate(t['rows']):
                    vals=[(x,amount(x)) for x in row[1:] if norm(x)]
                    if len(vals)==4 and all(v is not None for _,v in vals):cum.append((ri,label(row[0]),row[0],[vals[1],vals[3]]))
                names={p[1] for p in cum}
                if names&CORE['revenue'] and names&CORE['op_income'] and names&CORE['net_income']:income=(member,t,cum)
    if not bs or not income:return [],[],'반기 본표·누적 열 구조 확인 필요'
    basis='CFS' if '연결재무상태표' in norm(bs[1]['context']) else 'OFS'
    r={'corp_name':report['corp_name'],'stock_code':report['stock_code'],'period':f'{year}H1','period_type':'H1','fs_div':basis,'annualized':True,'data_source':'AUDIT_XML','fiscal_end':f'{year}-06','rcept_no':report['rcept_no'],'source_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+report['rcept_no'],'balance_tolerance':bs[1]['unit'],'roe_basis':'지배 순이익/기말 지배자본 연환산','icr_basis':'금융원가'}
    trace=[];values={}
    for group,keys in [(bs,['assets','liabilities','equity']),(income,['revenue','op_income','net_income'])]:
        member,t,ps=group
        if not t['unit']:return [],[],'반기 본표 단위 확인 필요'
        for key in keys:
            hits=[p for p in ps if p[1] in CORE[key]]
            if len(hits)!=1:return [],[],'반기 핵심 계정 중복·누락'
            ri,nm,raw,vals=hits[0];values[key]=[int(round(v*t['unit'])) for _,v in vals];r[key]=values[key][0]
            trace.append({'field':key,'table_index':t['index'],'row_index':ri,'row_label':raw,'current_token':vals[0][0],'prior_token':vals[1][0],'unit_multiplier':t['unit'],'xml_member':member,'comparison_basis':'손익: 전년 반기 누적 / 재무상태: 전년말'})
    if abs(r['assets']-r['liabilities']-r['equity'])>bs[1]['unit']:return [],[],'반기 자산 등식 검산 실패'
    def ratio(a,b):return round(a/b*100,2) if b>0 else float('nan')
    r['op_margin']=ratio(r['op_income'],r['revenue']);r['debt_ratio']=ratio(r['liabilities'],r['equity']);r['roa']=ratio(r['net_income']*2,r['assets'])
    r['sales_growth']=round((values['revenue'][0]/values['revenue'][1]-1)*100,2) if values['revenue'][1]>0 else float('nan')
    for key,aliases,group in [('net_income_owner',{'지배기업소유주지분','지배기업의소유주에게귀속되는당기순이익'},income),('equity_owner',{'지배기업소유주지분','지배기업의소유주에게귀속되는자본'},bs),('interest_expense',{'금융원가','금융비용'},income)]:
        member,t,ps=group;hits=[p for p in ps if p[1] in aliases]
        if key=='net_income_owner':
            headings=[i for i,row in enumerate(t['rows']) if row and norm(row[0])=='당기순이익의귀속']
            if len(headings)==1:hits=[p for p in hits if headings[0]<p[0]<=headings[0]+3]
        if len(hits)==1:
            ri,nm,raw,vals=hits[0];r[key]=abs(int(round(vals[0][1]*t['unit']))) if key=='interest_expense' else int(round(vals[0][1]*t['unit']))
            trace.append({'field':key,'table_index':t['index'],'row_index':ri,'row_label':raw,'current_token':vals[0][0],'prior_token':vals[1][0],'unit_multiplier':t['unit'],'xml_member':member})
    if r.get('equity_owner',0)>0 and 'net_income_owner' in r:r['roe']=ratio(r['net_income_owner']*2,r['equity_owner'])
    member,t,ps=bs;borrow=[p for p in ps if p[1] in BORROW]
    unknown=[p for p in ps if re.search('차입|사채',p[1]) and p[1] not in BORROW]
    unknown += [p for p in ps if p[3][0][1] and '금융부채' in p[1] and not re.search('매입|미지급|리스|파생',p[1])]
    if borrow and not unknown:
        r['borrowings']=sum(int(round(p[3][0][1]*t['unit'])) for p in borrow);r['borrow_dep']=ratio(r['borrowings'],r['assets'])
        for ri,nm,raw,vals in borrow:trace.append({'field':'borrowings_component','table_index':t['index'],'row_index':ri,'row_label':raw,'current_token':vals[0][0],'prior_token':vals[1][0],'unit_multiplier':t['unit'],'xml_member':member})
    if r.get('interest_expense',0)>0:r['icr']=round(r['op_income']/r['interest_expense'],2)
    for tr in trace:tr.update(corp_name=r['corp_name'],stock_code=r['stock_code'],period=r['period'],rcept_no=r['rcept_no'],source_url=r['source_url'])
    return [r],trace,'반기 누적 열·단위·자산 등식 검산 통과'
