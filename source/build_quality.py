"""기업·기간별 누락 계정과 차입금 매핑을 점검하고 불완전 지표를 비운다."""
from pathlib import Path
import json,re,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/processed';RAW=ROOT/'data/raw'

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    m=pd.read_csv(DATA/'metrics.csv',dtype={'stock_code':str,'period':str})
    mapping=pd.read_csv(DATA/'account_mapping.csv',dtype={'stock_code':str,'bsns_year':str,'reprt_code':str}).fillna('')
    rows=[]
    for i,r in m.iterrows():
        report='11012' if 'H' in r.period else '11011';year=r.period[:4]
        path=RAW/f'{r.stock_code}_{year}_{report}.json'
        raw=json.loads(path.read_text(encoding='utf-8')).get('list',[])
        maps=mapping[(mapping.stock_code==r.stock_code)&(mapping.bsns_year==year)&(mapping.reprt_code==report)]
        borrow_maps=maps[maps.account_key.isin(['borrow_current','borrow_current_lt','borrow_noncurrent','bonds','borrow_current_bonds','borrow_convertible','borrow_exchangeable'])]
        picked={(r.account_id,r.account_nm) for _,r in borrow_maps.iterrows() if r.account_id}
        unknown=[]
        for a in raw:
            if a.get('sj_div')!='BS':continue
            name=a.get('account_nm','');val=str(a.get('thstrm_amount','')).replace(',','').strip()
            if val in {'','-','0'}:continue
            if re.search('차입|사채',name) and not re.search('리스|대여|자산|할인발행차금|전환권|상환할증금',name):
                if (a.get('account_id'),name) not in picked:unknown.append(name)
        required=['revenue','op_income','assets','liabilities','equity','interest_expense','borrowings']
        missing=[c for c in required if pd.isna(r[c])]
        currencies={a.get('currency','KRW') for a in raw}-{''}
        bad_currency=bool(currencies-{'KRW','원'})
        balance_ok=all(pd.notna(r[c]) for c in ['assets','liabilities','equity']) and abs(r.assets-r.liabilities-r.equity)<=1
        borrow_ok=pd.notna(r.borrowings) and not unknown
        issues=[]
        if missing:issues.append('필수 계정 누락: '+','.join(missing))
        if unknown:issues.append('차입금 추가 매핑 검토: '+', '.join(sorted(set(unknown))))
        if bad_currency:issues.append('원화 이외 통화: '+','.join(currencies))
        if not balance_ok:issues.append('자산=부채+자본 대조 필요')
        if pd.notna(r.equity) and r.equity<=0:issues.append('자본 0 이하')
        if pd.notna(r.interest_expense) and r.interest_expense<=0:issues.append('이자비용·금융원가 0 이하')
        if not borrow_ok:
            m.loc[i,['borrowings','borrow_dep']]=float('nan')
        ready=not issues
        rows.append({'corp_name':r.corp_name,'stock_code':r.stock_code,'period':r.period,'fs_div':r.get('fs_div','CFS'),
                     'management_ready':'Y' if ready else 'N','borrowing_mapping':'완료' if borrow_ok else '확인 필요',
                     'icr_basis':r.icr_basis,'status':'자동 검산 통과·원문 추가 확인 권장' if ready else '; '.join(issues),
                     'source_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+str(raw[0].get('rcept_no','')) if raw else ''})
    m.to_csv(DATA/'metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(rows).to_csv(DATA/'data_quality.csv',index=False,encoding='utf-8-sig')
    q=pd.read_csv(DATA/'quarterly_metrics.csv',dtype={'stock_code':str,'period':str})
    bad={(r['stock_code'],r['period'][:4]) for r in rows if r['borrowing_mapping']!='완료'}
    for i,r in q.iterrows():
        if (r.stock_code,r.period[:4]) in bad:q.loc[i,['borrowings','borrow_dep']]=float('nan')
    q.to_csv(DATA/'quarterly_metrics.csv',index=False,encoding='utf-8-sig')
    print('품질표',len(rows),'행 · 관리 단계 판정 가능',sum(r['management_ready']=='Y' for r in rows),'행')

if __name__=='__main__':main()
