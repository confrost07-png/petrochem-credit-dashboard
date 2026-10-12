"""공시 원문 ZIP을 보존한다. 인증키나 인증키 포함 URL은 기록하지 않는다."""
from pathlib import Path
import json, sys, zipfile, io, argparse, time
import requests
from collect_expanded import read_key
from company_targets import registry
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/audit'; DATA=ROOT/'data/processed'

def collect(company=None,kinds=None,refresh=False):
    RAW.mkdir(parents=True,exist_ok=True)
    key=read_key()
    if not key: raise RuntimeError('비공개 .env의 DART_API_KEY가 필요합니다.')
    import pandas as pd
    metrics=pd.read_csv(DATA/'metrics.csv',dtype=str)
    if 'data_source' in metrics:metrics=metrics[metrics.data_source!='AUDIT_XML']
    targets=[c for c in registry() if (c['stock_code']==company if company else c['corp_name'] not in set(metrics.corp_name))]
    results=[]
    for c in targets:
        for kind in (kinds or ['F002','F001','A001']):
            cache=RAW/f"{c['corp_code']}_{kind}_list.json"
            if cache.exists() and not refresh: data=json.loads(cache.read_text(encoding='utf-8'))
            else:
                try:
                    r=requests.get('https://opendart.fss.or.kr/api/list.json',params={'crtfc_key':key,'corp_code':c['corp_code'],'bgn_de':'20240101','end_de':'20261007','pblntf_detail_ty':kind,'page_count':100,'last_reprt_at':'Y'},timeout=30)
                    r.raise_for_status();data=r.json()
                except requests.RequestException:
                    print(c['corp_name'],kind,'연결 실패');continue
                if data.get('status') not in ['000','013']:raise RuntimeError('공시목록 API 상태 '+str(data.get('status')))
                cache.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
                time.sleep(.3)
            for report in data.get('list',[])[:2]:
                receipt=report['rcept_no']; dest=RAW/f'{receipt}.zip'
                if not dest.exists():
                    try:
                        r=requests.get('https://opendart.fss.or.kr/api/document.xml',params={'crtfc_key':key,'rcept_no':receipt},timeout=45)
                        r.raise_for_status()
                    except requests.RequestException:
                        print(c['corp_name'],receipt,'원문 연결 실패');continue
                    if not zipfile.is_zipfile(io.BytesIO(r.content)):
                        print(c['corp_name'],receipt,'ZIP 미제공');continue
                    dest.write_bytes(r.content);time.sleep(.3)
                results.append({**report,**c,'document_path':str(dest.relative_to(ROOT)),'report_kind':kind})
            print(c['corp_name'],kind,data.get('status'),flush=True)
    index=DATA/'audit_report_index.csv'
    old=pd.read_csv(index,dtype=str).fillna('').to_dict('records') if index.exists() else []
    merged={r['rcept_no']:r for r in old+results}
    if merged:pd.DataFrame(merged.values()).to_csv(index,index=False,encoding='utf-8-sig')
    return results

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('--company');a=p.parse_args()
    print('원문 보존',len(collect(a.company)))
