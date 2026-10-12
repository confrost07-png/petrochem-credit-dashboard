"""업데이트 버튼으로 DART 호출 및 캐시 재정제를 수행한다."""
from pathlib import Path
import sys,runpy,io
from contextlib import redirect_stdout
ROOT=Path(__file__).resolve().parents[1]

def update_company(stock):
    sys.path.insert(0,str(ROOT/'source'))
    from collect_expanded import collect
    with redirect_stdout(io.StringIO()):
        result=collect(company=stock)
        # 일부 요청이 실패해도 성공한 원본은 즉시 화면용 CSV에 반영한다.
        result['audit_reports']=0
        if not (ROOT/'data/raw'/f'{stock}_2026_11012.json').exists() and not result['network_halted']:
            from collect_audit import collect as collect_originals
            from collect_expanded import read_key
            if read_key():result['audit_reports']=len(collect_originals(company=stock,kinds=['A002','F002','F001','A001'],refresh=True))
        if result['new_reports'] or result['selected_reports'] or result['audit_reports']:
            runpy.run_path(str(ROOT/'source/rebuild.py'))
    return result
