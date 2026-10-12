"""공시·기준·단위·주석 합계와 API 장부가를 일치시킨 차입금만 보완한다."""
import json,zipfile
import pandas as pd
from build_audit_metrics import ROOT,DATA,tables_from_document,norm,amount

def main():
    config=DATA/'verified_borrowings.json'
    if not config.exists():return
    specs=json.loads(config.read_text(encoding='utf-8'))
    index=pd.read_csv(DATA/'audit_report_index.csv',dtype=str)
    metrics=pd.read_csv(DATA/'metrics.csv',dtype={'stock_code':str,'period':str})
    quality=pd.read_csv(DATA/'data_quality.csv',dtype={'stock_code':str,'period':str})
    quarters=pd.read_csv(DATA/'quarterly_metrics.csv',dtype={'stock_code':str,'period':str})
    traces=[]
    cp=DATA/'verified_note_mapping.csv'
    cached=pd.read_csv(cp,dtype={'stock_code':str,'period':str}) if cp.exists() else pd.DataFrame(columns=['stock_code','period','amount'])
    for spec in specs:
        source=index[index.rcept_no==spec['rcept_no']]
        if len(source)!=1:raise ValueError('검증 주석 원문 누락')
        doc=ROOT/str(source.iloc[0].document_path).replace("\\","/")
        if not doc.exists():
            # 감사보고서 원문 zip이 없는 공유본: 이전에 원문과 대조해 저장한 주석 금액(verified_note_mapping.csv)을 재사용
            c=cached[(cached.stock_code==spec["stock_code"])&(cached.period==spec["period"])]
            if c.empty:raise ValueError("검증 주석 원문·이전 대조 결과 모두 없음")
            total=int(c.amount.sum());traces+=c.to_dict("records")
        else:
            total=0
            z=zipfile.ZipFile(doc)
            member=spec['rcept_no']+'.xml'
            tables={t['index']:t for t in tables_from_document(z.read(member))}
            raw=json.loads((ROOT/'data/raw'/f"{spec['stock_code']}_{spec['period'][:4]}_11012.json").read_text(encoding='utf-8'))
            if raw['_collection']['fs_div']!=spec['fs_div'] or raw['list'][0]['rcept_no']!=spec['rcept_no']:raise ValueError('주석과 API 기준·공시 불일치')
            total=0
            for part in spec['tables']:
                t=tables[part['index']]
                if not t['unit'] or norm(''.join(t['rows'][0]))!='구분당반기말전기말':raise ValueError('주석 단위·기간 열 변경')
                rows={norm(row[0]):row for row in t['rows'][1:] if len(row)==3}
                if set(rows)!=set(part['components'])|{'합계'}:raise ValueError('주석 구성 변경')
                subtotal=0
                for name in part['components']:
                    value=amount(rows[name][1])
                    if value is None or value<0:raise ValueError('장부금액 확인 필요')
                    won=int(round(value*t['unit']));subtotal+=won
                    traces.append({**{k:spec[k] for k in ['stock_code','corp_name','period','rcept_no','fs_div']},'xml_member':member,'table_index':t['index'],'row_label':name,'raw_token':rows[name][1],'unit_multiplier':t['unit'],'amount':won,'source_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+spec['rcept_no']})
                account=[r for r in raw['list'] if r['sj_div']=='BS' and norm(r['account_nm'])==part['bs_account']]
                if len(account)!=1 or subtotal!=int(amount(account[0]['thstrm_amount'])) or subtotal!=int(amount(rows['합계'][1])*t['unit']):raise ValueError('주석 합계·API 금융부채 대조 실패')
                total+=subtotal
        hit=(metrics.stock_code==spec['stock_code'])&(metrics.period==spec['period']);r=metrics[hit].iloc[0]
        metrics.loc[hit,'borrowings']=total;metrics.loc[hit,'borrow_dep']=round(total/r.assets*100,2)
        required=['revenue','op_income','assets','liabilities','equity','interest_expense']
        ready=r[required].notna().all() and r.equity>0 and r.interest_expense>0 and abs(r.assets-r.liabilities-r.equity)<=1
        qhit=(quality.stock_code==spec['stock_code'])&(quality.period==spec['period'])
        quality.loc[qhit,'borrowing_mapping']='완료 · 원문 주석 대조';quality.loc[qhit,'management_ready']='Y' if ready else 'N'
        quality.loc[qhit,'status']='주석 차입금·사채 합계 = API 단기·장기 금융부채 장부가 검증 통과' if ready else '주석 차입금 확인 · 기타 필수 계정 검토 필요'
        qhit=(quarters.stock_code==spec['stock_code'])&quarters.period.isin([spec['period'],spec['period'][:4]+'Q2'])
        quarters.loc[qhit,'borrowings']=total
        quarters.loc[qhit,'borrow_dep']=(total/quarters.loc[qhit,'assets']*100).round(2)
    metrics.to_csv(DATA/'metrics.csv',index=False,encoding='utf-8-sig');quality.to_csv(DATA/'data_quality.csv',index=False,encoding='utf-8-sig');quarters.to_csv(DATA/'quarterly_metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(traces).to_csv(DATA/'verified_note_mapping.csv',index=False,encoding='utf-8-sig')

if __name__=='__main__':main()
