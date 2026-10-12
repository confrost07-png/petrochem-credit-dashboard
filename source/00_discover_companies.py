"""사업보고서 제출기업 전수 조회 후 정유·석유화학 업종 목록을 만든다.

범위: 2022-01-01~2026-09-30에 사업보고서를 제출한 기업의 현재 DART
업종코드 192*, 20111, 20119, 202* + 한국화학산업협회 회원사.
전수의 의미는 위 기간·업종으로 한정한다. 공시기업 전체와 전 산업 전체는 다르다.
검색·기업개황 응답은 .deck_work/discovery에 캐시한다. 인증키는 저장하지 않는다.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import calendar, csv, io, json, os, re, sys, time, zipfile, html, argparse, threading
import xml.etree.ElementTree as ET
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.deck_work' / 'discovery'
OUT = ROOT / 'data' / 'processed'
BASE = 'https://opendart.fss.or.kr/api/'
MEMBERS = 'https://kcia.kr/member-company-information/about-member-companies/member-company'
KEY = dotenv_values(ROOT / '.env').get('DART_API_KEY', '')

def api(endpoint, params, cache_name):
    path = CACHE / cache_name
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    for attempt in range(3):
        try:
            r = requests.get(BASE + endpoint, params={'crtfc_key': KEY, **params}, timeout=45)
            data = r.json()
            if data.get('status') not in {'000','013'}:
                raise RuntimeError('DART status ' + str(data.get('status')))
            path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            time.sleep(.12)
            return data
        except (requests.RequestException,ValueError):
            if attempt == 2: raise RuntimeError('DART 요청 실패(인증키와 URL은 출력하지 않음)') from None
            time.sleep(1)

def normalize(name):
    return re.sub(r'주식회사|\(주\)|㈜|[\s·.,&()_-]', '', name).casefold()

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if not KEY or KEY == 'YOUR_API_KEY': raise SystemExit('DART_API_KEY 설정 필요')
    CACHE.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    filings = {}
    for y in range(2022,2027):
        for m in (1,4,7,10):
            if y == 2026 and m == 10: continue
            endm=m+2
            p={'bgn_de':f'{y}{m:02}01','end_de':f'{y}{endm:02}{calendar.monthrange(y,endm)[1]}',
               'pblntf_detail_ty':'A001','last_reprt_at':'Y','page_count':'100'}
            first=api('list.json',{**p,'page_no':1},f'filings_{y}_{m}_1.json')
            pages=[first]
            with ThreadPoolExecutor(max_workers=4) as pool:
                jobs=[pool.submit(api,'list.json',{**p,'page_no':n},f'filings_{y}_{m}_{n}.json')
                      for n in range(2,int(first.get('total_page',0))+1)]
                pages.extend(j.result() for j in as_completed(jobs))
            for page in pages:
                for row in page.get('list',[]): filings[row['corp_code']]=row
            print(f'사업보고서 목록 {y}/{m}: 누적 {len(filings)}개 기업',flush=True)

    # 협회 회원 전체를 함께 조회: 사업보고서 API 미제공 회원도 목록에 남긴다.
    htmlpath=CACHE/'association.html'
    if not htmlpath.exists():
        r=requests.get(MEMBERS,timeout=40); r.raise_for_status();r.encoding='utf-8'
        htmlpath.write_text(r.text,encoding='utf-8')
    text=re.sub(r'\s+',' ',re.sub('<[^>]*>',' ',htmlpath.read_text(encoding='utf-8')))
    member_names=[x.split('/')[0].strip() for x in re.findall(r'회사명 (.*?) 사이트주소',text)]
    # DART 최신 회사명과 협회명 사이 명칭 변경만 명시적으로 연결한다.
    parser=argparse.ArgumentParser()
    parser.add_argument('--public-profiles',action='store_true',help='공개 기업개황 웹페이지로 세부 업종 확인(API 연결 장애 시)')
    parser.add_argument('--offline',action='store_true',help='캐시로 목록만 갱신하고 미조회 기업을 대기로 표시')
    args=parser.parse_args()
    aliases={'한국알콜산업':'한국알콜','코오롱인더스트리':'코오롱인더',
             'sk지오센트릭':'에스케이지오센트릭','skpicglobal':'에스케이피아이씨글로벌',
             'lxmma':'엘엑스엠엠에이','dl케미칼':'DL케미칼',
             '에이치앤엘어드밴스드':'에이치디현대케미칼'}
    xmlpath=CACHE/'corp_codes.xml'
    if not xmlpath.exists():
        r=requests.get(BASE+'corpCode.xml',params={'crtfc_key':KEY},timeout=60)
        if not zipfile.is_zipfile(io.BytesIO(r.content)): raise RuntimeError('고유번호 응답 오류')
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            xmlpath.write_bytes(z.read(next(n for n in z.namelist() if n.lower().endswith('.xml'))))
    allcodes=[{c.tag:(c.text or '').strip() for c in x} for x in ET.parse(xmlpath).getroot().iter('list')]
    members={}
    unresolved=[]
    for name in member_names:
        norm=normalize(name); lookup=normalize(aliases.get(norm,name))
        hits=[x for x in allcodes if normalize(x['corp_name']) in {norm,lookup}]
        if len(hits)>1:
            current=[x for x in hits if x['corp_code'] in filings]
            if len(current)==1:hits=current
        if len(hits)==1:
            c=hits[0];members[c['corp_code']]=name;filings.setdefault(c['corp_code'],c)
        else: unresolved.append({'member_name':name,'matches':len(hits)})
    # 정유 사업을 가진 복합기업 및 주요 정유법인은 업종코드 외에도 연결한다.
    extra={'SK이노베이션','SK에너지','SK인천석유화학','에이치디현대오일뱅크'}
    extras={x['corp_code'] for x in allcodes if x['corp_name'] in extra}
    for x in allcodes:
        if x['corp_code'] in extras: filings.setdefault(x['corp_code'],x)
    profiles=[]; failures=[]
    stop_network=threading.Event();failure_lock=threading.Lock();failure_count=[0]
    def profile(code):
        cached=CACHE/f'company_{code}.json'
        if cached.exists():
            p=json.loads(cached.read_text(encoding='utf-8'))
            # DART API의 201 같은 대분류는 석유화학임을 확정할 수 없어 웹 세부 업종 확인.
            if len(p.get('induty_code',''))>=5 or p.get('induty_code','').startswith(('192','202')) or not p.get('induty_code','').startswith(('19','20')):
                p['industry_name']='';return p
        path=CACHE/f'popup_{code}.json'
        if path.exists():return json.loads(path.read_text(encoding='utf-8'))
        if args.offline:raise RuntimeError('기업개황 캐시 없음')
        if stop_network.is_set():raise RuntimeError('연속 연결 실패 후 조회 중단')
        if not args.public_profiles and not cached.exists():
            p=api('company.json',{'corp_code':code},f'company_{code}.json')
            ind=p.get('induty_code','')
            if len(ind)>=5 or ind.startswith(('192','202')) or not ind.startswith(('19','20')):
                p['industry_name']='';return p
        url='https://dart.fss.or.kr/dsae001/selectPopup.ax'
        r=requests.get(url,params={'selectKey':code},timeout=30);r.raise_for_status();r.encoding='utf-8'
        values={}
        for th,td in re.findall(r'<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>',r.text,re.S):
            clean=lambda t:html.unescape(re.sub(r'\s+',' ',re.sub('<[^>]*>',' ',t))).strip()
            values[clean(th)]=clean(td)
        if not values.get('업종명'):raise RuntimeError('공개 기업개황 업종 미제공')
        names={'원유 정제처리업':'19210','윤활유 및 그리스 제조업':'19221',
               '기타 석유정제물 재처리업':'19229','석유화학계 기초 화학물질 제조업':'20111',
               '석탄화학계 화합물 및 기타 기초 유기 화학물질 제조업':'20119',
               '합성고무 제조업':'20201','합성수지 및 기타 플라스틱 물질 제조업':'20202',
               '혼성 및 재생 플라스틱 소재 물질 제조업':'20203'}
        kind=values.get('법인구분','')
        p={'corp_code':code,'corp_name':values.get('공시회사명',filings[code]['corp_name']),
           'stock_code':values.get('종목코드',''),'induty_code':names.get(values['업종명'],''),
           'industry_name':values['업종명'],'corp_cls':{'유가증권시장':'Y','코스닥시장':'K','코넥스시장':'N'}.get(kind,'E'),
           'profile_source':url+'?selectKey='+code}
        path.write_text(json.dumps(p,ensure_ascii=False),encoding='utf-8');time.sleep(.25);return p
    def safe_profile(code):
        try:return profile(code)
        except (requests.RequestException,RuntimeError) as exc:
            msg=str(exc)
            if isinstance(exc,requests.RequestException) or 'DART 요청 실패' in msg or 'DART status' in msg:
                with failure_lock:
                    failure_count[0]+=1
                    if failure_count[0]>=3 or any(('status '+c) in msg for c in ('010','011','012','020','800','901')):
                        stop_network.set()
            raise RuntimeError('기업개황 조회 실패 또는 대기') from None
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(safe_profile,code):code for code in filings}
        for i,j in enumerate(as_completed(jobs),1):
            try: profiles.append(j.result())
            except Exception: failures.append(jobs[j])
            if i%250==0: print(f'기업개황 확인 {i}/{len(jobs)} · 실패 {len(failures)}',flush=True)
    # 기업개황 미조회 회원·정유사는 고유번호로 목록에 포함하되 업종 확인 상태를 남긴다.
    profile_codes={p.get('corp_code') for p in profiles}
    for code in (set(members)|extras)-profile_codes:
        x=next(x for x in allcodes if x['corp_code']==code)
        profiles.append({'corp_code':code,'corp_name':x['corp_name'],'stock_code':x.get('stock_code',''),
                         'induty_code':'','corp_cls':'','industry_name':'기업개황 연결 실패·확인 대기'})
    rows=[]
    for p in profiles:
        code=p.get('corp_code','');ind=p.get('induty_code','')
        if not (ind.startswith(('192','202')) or ind in {'20111','20119'} or code in members or code in extras):continue
        original=next((x for x in allcodes if x['corp_code']==code),{})
        name=original.get('corp_name',p['corp_name']); stock=p.get('stock_code','').strip()
        if not re.fullmatch(r'\d{6}',stock):stock=''
        name={'금호석유':'금호석유화학'}.get(name,name)
        category='정유·석유제품' if ind.startswith('192') or code in extras else '석유화학'
        if code in extras and '이노베이션' in name:category='복합기업(정유 포함)'
        if code in members and not (ind.startswith('202') or ind in {'20111','20119'} or ind.startswith('192')):
            category='석유화학(협회 회원·세부업종 확인 대기)'
        if name in {'S-Oil','GS칼텍스','SK에너지','SK인천석유화학','에이치디현대오일뱅크'}:
            category='정유·석유제품'
        rows.append({'corp_name':name,'stock_code':stock or 'D'+code,'listed_stock_code':stock,
                     'corp_code':code,'category':category,'industry_code':ind,
                     'corp_cls':p.get('corp_cls',''),'industry_name':p.get('industry_name',''),
                     'association_member':'Y' if code in members else 'N',
                     'selection_basis':'DART 업종코드' if code not in (set(members)|extras) else 'DART 업종·협회·정유법인',
                     'source_url':MEMBERS if code in members else 'https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002'})
    rows.sort(key=lambda r:(r['category'],r['corp_name']))
    # 중복 식별자 금지. API 오류가 있으면 전수 조회 완료로 표시하지 않는다.
    assert len({r['corp_code'] for r in rows})==len(rows)
    with (OUT/'company_registry.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    meta={'filing_window':'2022-01-01~2026-09-30','industry_codes':['192*','20111','20119','202*'],
          'filing_companies':len(filings),'profile_success':len(filings)-len(failures),'profile_failed':failures,
          'association_members':len(member_names),'unresolved_members':unresolved,'selected_companies':len(rows),
          'complete':not failures and not unresolved,'as_of':'2026-10-07',
          'limit':'현재 DART 업종 기준. 기간 밖 공시·사업보고서 미제출 감사보고서 전용 법인은 전수범위 밖. 협회 회원은 별도 포함.'}
    (OUT/'universe_status.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    # 연결 실패 기업은 누락하지 않고 재시도할 전수 목록으로 별도 보관한다.
    pending=[{'corp_code':code,'corp_name':filings[code]['corp_name'],'stock_code':filings[code].get('stock_code',''),
              'status':'기업개황 확인 대기'} for code in failures]
    if pending:
        with (OUT/'company_universe_pending.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(pending[0]));w.writeheader();w.writerows(pending)
    # 관련 명칭의 미조회 기업도 후보 목록에 노출한다. 업종 확정 기업으로 세지 않는다.
    known={r['corp_code'] for r in rows}
    candidates=[]
    for frow in pending:
        if frow['corp_code'] in known or not re.search('석유|유화|화학|케미칼|폴리',frow['corp_name']):continue
        x=next((x for x in allcodes if x['corp_code']==frow['corp_code']),None)
        if not x:continue
        candidates.append({'corp_name':x['corp_name'],'stock_code':x.get('stock_code','') or 'D'+x['corp_code'],
             'listed_stock_code':x.get('stock_code',''),'corp_code':x['corp_code'],
             'category':'업종 확인 대기(공시 후보)','industry_code':'','industry_name':'명칭 기반 후보·업종 미확정',
             'corp_cls':'','association_member':'N','selection_basis':'공시 전수목록의 관련 기업명·업종 확인 필요',
             'source_url':'https://dart.fss.or.kr/dsae001/selectPopup.ax?selectKey='+x['corp_code']})
    with (OUT/'company_candidates.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(candidates)
    print('기업 목록',len(rows),'개 · 기업개황 확인',meta['profile_success'],'개 · 재시도',len(failures),
          '개 · 미해결 회원',len(unresolved),'개 · 전수 확인 완료',meta['complete'],flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('기업 목록 수집 중단:',type(exc).__name__, '(인증키와 요청 URL은 출력하지 않음)',flush=True)
        raise SystemExit(1) from None
