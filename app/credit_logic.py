"""여신 계기판 규칙. 관리 단계는 참고용이며 대출 가부를 뜻하지 않는다."""
from math import isfinite

RESPONSES = {
    '정상 관리': '정기 점검 및 업종 한도 점검 검토',
    '관찰 (빚 부담)': '분기별 차입금 증감·단기차입 비중 점검 검토',
    '관리 강화 (이익 부족)': '만기연장·금리조정 조건 및 다음 분기 일회성 여부 확인 검토',
    '집중 관리': '담보·보증 보강 및 사업재편 조건부 지원 검토',
    '판정 보류': '누락 계정·차입금 구성·자본 상태 확인 검토',
}
STAGE_COLORS = {'정상 관리':'#087f73','관찰 (빚 부담)':'#b76b16',
                '관리 강화 (이익 부족)':'#bc6728','집중 관리':'#b63546','판정 보류':'#657586'}

def valid(value):
    try: return isfinite(float(value))
    except (TypeError,ValueError): return False

def stage(icr, borrow_dep, equity=1, threshold=30, ready=True):
    if not ready or not all(valid(v) for v in (icr,borrow_dep,equity)) or equity<=0 or borrow_dep<0:
        return '판정 보류'
    if icr>=1: return '정상 관리' if borrow_dep<threshold else '관찰 (빚 부담)'
    return '관리 강화 (이익 부족)' if borrow_dep<threshold else '집중 관리'

def headroom(icr):
    return (1-1/icr)*100 if valid(icr) and icr>1 else None

def stress(icr, op_income, decrease=0, increase=0, historical_change=None):
    """이미 적자인 기업은 감소율 적용으로 손실이 줄어드는 오류를 방지한다."""
    if not valid(icr) or not valid(op_income): return None
    if op_income<=0: return float(icr)
    factor=1+historical_change if historical_change is not None else 1-decrease
    return float(icr)*factor/(1+increase)

def loss_streak(records, corp, selected_period):
    # H1은 독립된 추가 연도로 세지 않고 직전 확정 연간까지만 센다.
    year=int(selected_period[:4])-(1 if 'H' in selected_period else 0)
    lookup={str(r['period']):r['icr'] for r in records
            if r['corp_name']==corp and str(r['period']).isdigit()}
    count=0
    while str(year) in lookup and valid(lookup[str(year)]) and lookup[str(year)]<1:
        count+=1;year-=1
    return count

def clip_icr(value, low=-5, high=15):
    if not valid(value): return None,''
    return max(low,min(high,float(value))),('←' if value<low else '→' if value>high else '')
