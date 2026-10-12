"""이미 등록한 기업의 상장 구분만 재확인한다. 전 업종 수천 개 재요청을 하지 않는다."""
from pathlib import Path
import csv,json,time,requests
from collect_expanded import read_key,FATAL
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/processed';CACHE=ROOT/'.deck_work/discovery'

def main():
    key=read_key();success=set();halt=False
    if not key:raise SystemExit('DART_API_KEY 필요')
    for name in ('company_registry.csv','company_candidates.csv'):
        path=DATA/name
        with path.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        for r in rows:
            if r.get('corp_cls') or halt:continue
            try:
                reply=requests.get('https://opendart.fss.or.kr/api/company.json',params={'crtfc_key':key,'corp_code':r['corp_code']},timeout=20)
                reply.raise_for_status();p=reply.json()
            except (requests.RequestException,ValueError):halt=True;break
            if p.get('status')=='000':
                r['corp_cls']=p.get('corp_cls','')
                if not r.get('industry_code'):r['industry_code']=p.get('induty_code','')
                if '연결 실패' in r.get('industry_name',''):r['industry_name']='세부 업종 확인 필요' if len(r.get('industry_code',''))<5 else ''
                (CACHE/f"company_{r['corp_code']}.json").write_text(json.dumps(p,ensure_ascii=False),encoding='utf-8')
                success.add(r['corp_code'])
            elif p.get('status') in FATAL:halt=True
            time.sleep(.8)
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    meta_path=DATA/'universe_status.json'
    if meta_path.exists():
        m=json.loads(meta_path.read_text(encoding='utf-8'))
        old=set(m['profile_failed']);removed=old&success
        m['profile_failed']=[code for code in m['profile_failed'] if code not in success]
        m['profile_success']+=len(removed)
        meta_path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    pending=DATA/'company_universe_pending.csv'
    if pending.exists():
        with pending.open(encoding='utf-8-sig') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        with pending.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(r for r in rows if r['corp_code'] not in success)
    print('등록 기업 개황 추가 확인',len(success),'건 · 중단',halt)

if __name__=='__main__':main()
