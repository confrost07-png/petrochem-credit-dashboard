"""전체 기업 원본 수집. 키는 .env에서 읽으며 원본 캐시로 키 없이 재현할 수 있다.
python source/collect_expanded.py --company 010950 (S-OIL)
python source/collect_expanded.py --all
CFS 미제공(013)일 때만 OFS를 요청한다. 오류는 결측값 0으로 대체하지 않는다.
"""
from pathlib import Path
import argparse,csv,json,time,sys
from datetime import datetime,timezone
import requests
from dotenv import dotenv_values
from company_targets import registry

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw';DATA=ROOT/'data/processed'
URL='https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json'
JOBS=[(2026,'11012','2026H1'),(2025,'11011','2025'),(2026,'11013','2026Q1')]+[(y,'11011',str(y)) for y in range(2024,2020,-1)]
FATAL={'010','011','012','020','021','800','901'}
STATUS_NOTES={'010':'등록되지 않은 인증키','011':'사용 중지된 인증키','012':'DART 등록 IP 접근 제한',
              '020':'DART 요청 한도 초과','021':'조회 기업 수 제한','800':'DART 시스템 점검','901':'DART 계정 보유기간 만료',
              '100':'요청 인자 오류','101':'부적절한 API 접근','900':'DART 서버 오류'}

def read_key():
    key=(dotenv_values(ROOT/'.env',encoding='utf-8-sig').get('DART_API_KEY') or '').strip()
    return '' if key=='YOUR_API_KEY' else key

def diagnose():
    """키 값·요청 URL을 저장하지 않고 연결 단계와 인증 응답만 기록한다."""
    key=read_key()
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'key_loaded':bool(key),
            'key_format_ok':len(key)==40,'homepage_status':'','api_status':'NOT_TESTED','note':''}
    try:
        reply=requests.get('https://opendart.fss.or.kr/',timeout=15)
        result['homepage_status']=str(reply.status_code)
    except requests.RequestException:
        result['homepage_status']='CONNECTION_FAILED'
    if not key:result.update(api_status='NO_KEY',note='.env에서 DART_API_KEY를 찾지 못했습니다.')
    else:
        try:
            reply=requests.get('https://opendart.fss.or.kr/api/company.json',
                params={'crtfc_key':key,'corp_code':'00356361'},timeout=15)
            reply.raise_for_status();data=reply.json()
            code=str(data.get('status','INVALID_RESPONSE'))
            result.update(api_status=code,note='인증키와 기업개황 API 정상 응답' if code=='000' else STATUS_NOTES.get(code,'API 응답 확인 필요'))
        except (requests.RequestException,ValueError):
            result.update(api_status='NETWORK_ERROR',note='인증 결과를 받기 전 연결 실패. 키 오류·공시 미제공으로 판정할 수 없습니다.')
    DATA.mkdir(parents=True,exist_ok=True)
    (DATA/'dart_connection_status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def write_csv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def fetch(corp,year,report,key):
    path=RAW/f"{corp['stock_code']}_{year}_{report}.json"
    if path.exists():
        data=json.loads(path.read_text(encoding='utf-8'))
        rows=data.get('list',[])
        return {'status':data.get('status',''),'fs_div':data.get('_collection',{}).get('fs_div',rows[0].get('fs_div','CFS') if rows else ''),
                'rows':len(rows),'rcept_no':rows[0].get('rcept_no','') if rows else '', 'note':'원본 캐시'}
    if not key or key=='YOUR_API_KEY':return {'status':'NO_KEY','fs_div':'','rows':0,'rcept_no':'','note':'키 없음·원본 없음'}
    for basis in ('CFS','OFS'):
        try:
            r=requests.get(URL,params={'crtfc_key':key,'corp_code':corp['corp_code'],'bsns_year':str(year),
                                       'reprt_code':report,'fs_div':basis},timeout=30)
            r.raise_for_status();data=r.json()
        except (requests.RequestException,ValueError):
            return {'status':'NETWORK_ERROR','fs_div':basis,'rows':0,'rcept_no':'','note':'DART 연결 실패·재시도 필요'}
        time.sleep(.7)
        status=str(data.get('status',''))
        rows=data.get('list',[])
        if status=='000':
            if not rows:return {'status':'EMPTY_RESPONSE','fs_div':basis,'rows':0,'rcept_no':'','note':'정상 코드지만 계정 목록 없음·재확인 필요'}
            # API 응답 계정은 보존하고, 요청한 연결/별도 기준만 별도 메타데이터로 기록한다.
            data['_collection']={'fs_div':basis,'collected_at':datetime.now(timezone.utc).isoformat()}
            path.write_text(json.dumps(data,ensure_ascii=False,indent=1),encoding='utf-8')
            return {'status':status,'fs_div':basis,'rows':len(rows),'rcept_no':rows[0].get('rcept_no',''),
                    'note':'연결재무제표' if basis=='CFS' else '연결 미제공·별도재무제표'}
        if status!='013':return {'status':status,'fs_div':basis,'rows':0,'rcept_no':'','note':STATUS_NOTES.get(status,'DART 응답 오류(인증키 미출력)')}
    return {'status':'013','fs_div':'','rows':0,'rcept_no':'','note':'연결·별도 API 재무제표 미제공'}

def collect(company=None,all_companies=False):
    RAW.mkdir(parents=True,exist_ok=True);DATA.mkdir(parents=True,exist_ok=True)
    key=read_key()
    corps=registry();old={}
    # 확인된 상장기업과 종목코드가 있는 기업부터 수집한다.
    corps=sorted(corps,key=lambda c:(c.get('corp_cls') not in ('Y','K'),not c['stock_code'].isdigit(),c['corp_name']))
    coverage=DATA/'collection_coverage.csv'
    if coverage.exists():
        with coverage.open(encoding='utf-8-sig') as f:old={(r['stock_code'],r['period']):r for r in csv.DictReader(f)}
    rows=[];network_failures=0;halt=False;halt_reason='';new_reports=0;selected_reports=0
    for corp in corps:
        wanted=all_companies or corp['stock_code']==company
        for y,report,period in JOBS:
            base={k:corp[k] for k in ('corp_name','stock_code','corp_code')}
            base.update(period=period,year=y,report_code=report)
            path=RAW/f"{corp['stock_code']}_{y}_{report}.json"
            was_cached=path.exists()
            if was_cached or (wanted and not halt):
                result=fetch(corp,y,report,key)
                if result['status']=='000' and wanted:
                    selected_reports+=1
                    if not was_cached:new_reports+=1
                if result['status']=='NETWORK_ERROR':network_failures+=1
                else:network_failures=0
                if result['status'] in FATAL or result['status']=='NO_KEY' or network_failures>=3:
                    halt=True;halt_reason=result['status']
            else:
                result=old.get((corp['stock_code'],period),{'status':'PENDING','fs_div':'','rows':0,'rcept_no':'','note':'미수집·기업 업데이트로 재시도'})
                result={k:result.get(k,'') for k in ('status','fs_div','rows','rcept_no','note')}
                if wanted and halt and result['status'] in ('PENDING','DEFERRED_NETWORK','DEFERRED_API'):
                    result.update(status='DEFERRED_NETWORK' if halt_reason=='NETWORK_ERROR' else 'DEFERRED_API',
                                  note='앞선 연결·인증 요청 실패로 미시도. 공시 미제공(013)이 아닙니다.')
            rows.append({**base,**result})
        if wanted:print(corp['corp_name'],'·',','.join(r['status'] for r in rows[-7:]),flush=True)
    write_csv(coverage,rows)
    write_csv(RAW/'corp_codes.csv',[{k:c[k] for k in ('stock_code','corp_name','corp_code')} for c in corps])
    logs=[{**r,'source_file':f"{r['stock_code']}_{r['year']}_{r['report_code']}.json" if r['status']=='000' else ''} for r in rows]
    write_csv(RAW/'expanded_collect_log.csv',logs)
    return {'reports':sum(r['status']=='000' for r in rows),'network_halted':halt,'halt_reason':halt_reason,
            'new_reports':new_reports,'selected_reports':selected_reports,'companies':len(corps)}

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('--company');p.add_argument('--all',action='store_true');p.add_argument('--diagnose',action='store_true');a=p.parse_args()
    if a.diagnose:print(diagnose())
    elif a.company or a.all:print(collect(a.company,a.all))
    else:p.error('--company, --all 또는 --diagnose를 지정하세요.')
