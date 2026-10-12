"""
04_compare.py : 기업 비교 데이터 (연도별 3사 지표를 나란히 + 3사 간 최대-최소 차이)

입력 : data/processed/metrics.csv
출력 : data/processed/company_comparison.csv
       period, metric, metric_name, unit, 롯데케미칼, 대한유화, 금호석유화학, max_corp, min_corp, gap, gap_unit, annualized
- 비율 지표의 차이는 %p, 이자보상배율 차이는 배.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
CORPS = ["롯데케미칼", "대한유화", "금호석유화학"]
METRICS = [
    ("sales_growth", "매출 성장률", "%", "%p"),
    ("op_margin", "영업이익률", "%", "%p"),
    ("roa", "ROA", "%", "%p"),
    ("roe", "ROE", "%", "%p"),
    ("debt_ratio", "부채비율", "%", "%p"),
    ("icr", "이자보상배율", "배", "배"),
    ("borrow_dep", "차입금 의존도", "%", "%p"),
]


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    path = PROC / "metrics.csv"
    if not path.exists():
        sys.exit("[중단] metrics.csv 가 없습니다. 03_metrics.py 를 먼저 실행하세요.")
    m = pd.read_csv(path, dtype={"stock_code": str, "period": str}, encoding="utf-8-sig")
    global CORPS
    CORPS=m.corp_name.drop_duplicates().tolist()

    rows = []
    for period in sorted(m.period.unique()):
        sub = m[m.period == period].set_index("corp_name")
        for key, name, unit, gap_unit in METRICS:
            vals = {c: sub[key].get(c) for c in CORPS}
            valid = {c: v for c, v in vals.items() if pd.notna(v)}
            mx = max(valid, key=valid.get) if valid else ""
            mn = min(valid, key=valid.get) if valid else ""
            gap = round(valid[mx] - valid[mn], 2) if valid else None
            annual = sub["annualized"].iloc[0] if key in ("roa", "roe") and len(sub) else "N"
            rows.append({"period": period, "metric": key, "metric_name": name, "unit": unit, **vals,
                         "max_corp": mx, "min_corp": mn, "gap": gap, "gap_unit": gap_unit, "annualized": annual})

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "company_comparison.csv", index=False, encoding="utf-8-sig")
    print(f"[완료] company_comparison.csv {len(out)}행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
