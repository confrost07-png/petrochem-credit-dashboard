"""수집 실패와 실제 API 미제공을 구분하는 화면 문구."""
STATUS_TEXT = {
    'NETWORK_ERROR': 'DART 연결 실패 · 인증/공시 여부 미확인',
    'DEFERRED_NETWORK': '연결 장애로 아직 조회하지 못함',
    'DEFERRED_API': '인증·요청 제한 때문에 아직 조회하지 못함',
    'PENDING': '재무제표 미수집',
    'NO_KEY': '.env의 DART_API_KEY 필요',
    '010': 'DART 인증키 미등록', '011': 'DART 인증키 사용 중지',
    '012': 'DART 등록 IP 접근 제한', '020': 'DART 요청 한도 초과',
    '013': 'DART API에서 연결·별도 재무제표 미제공 · 공시 원문 별도 확인 필요',
    '100': 'DART 요청 인자 오류', '800': 'DART 시스템 점검',
    '901': 'DART 계정 보유기간 만료',
    '000': '원본 수집됨 · 정제·계정 매핑 확인 필요',
}

def missing_message(name, period, coverage=None, metrics=None):
    message = '재무제표 미수집'
    if coverage is not None and not coverage.empty:
        hit=coverage[(coverage.corp_name==name)&(coverage.period.astype(str)==str(period))]
        if not hit.empty:
            code=str(hit.iloc[-1]['status'])
            message=STATUS_TEXT.get(code,'DART 응답 '+code+' · 확인 필요')
    available=[]
    if metrics is not None and not metrics.empty:
        available=metrics.loc[metrics.corp_name==name,'period'].astype(str).tolist()
    suffix=' · 제공 기간: '+', '.join(available) if available else ''
    return f'{name} · {period}: {message} · 판정 보류{suffix}'
