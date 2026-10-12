"""수집된 원본으로 전체 지표를 재현한다. API 키 없이 실행 가능."""
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source'))
for name in ['02_clean.py','03_metrics.py','03b_quarterly.py','build_quality.py','build_audit_metrics.py','apply_verified_notes.py','04_compare.py','build_reconciliation.py']:
    module=runpy.run_path(str(ROOT/'source'/name))
    result=module['main']()
    if result not in (None,0):raise SystemExit('정제 단계 실패: '+name)
