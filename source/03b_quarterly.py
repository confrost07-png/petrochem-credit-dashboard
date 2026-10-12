"""
03b_quarterly.py : 심화 분석 "2026 호르무즈 충격 분기"용 분기·반기 지표

입력 : data/processed/financials_clean.csv
출력 : data/processed/quarterly_metrics.csv

규칙
- 매출 성장률(sales_growth_yoy) = 해당 기간 매출 / 전년 같은 기간 매출 - 1 (2026 행만)
- 영업이익률 = 해당 기간 영업이익 / 해당 기간 매출
- ROA·ROE 연환산 = 순이익 x 4(분기) 또는 x 2(반기) / 기말 자산·지배기업 소유주지분 (2026 행만)
- 부채비율·차입금 의존도 = 3월 말·6월 말 시점 값. 2025 분기 말 재무상태표는 2026 보고서에 없어 빈칸
  (2025년 말 값은 metrics.csv 의 2025 FY 행을 쓴다)
- 이자보상배율 = 해당 기간 영업이익 / 해당 기간 이자비용(없으면 금융원가)
- 2분기 단독 = 반기보고서의 3개월 금액. "반기 누적 - 1분기"와의 대조는 check_log.csv (02_clean) 참고
- 비교 기준: 2026Q1 vs 2025Q1 은 1분기보고서끼리, 2026Q2·H1 vs 2025Q2·H1 은 반기보고서끼리 비교한다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

# 03_metrics.py 의 공통 함수를 그대로 쓴다 (산식이 두 곳에서 달라지지 않게)
_spec = importlib.util.spec_from_file_location("metrics03", Path(__file__).resolve().parent / "03_metrics.py")
m03 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m03)

PERIODS = ["2025Q1", "2025Q2", "2026Q1", "2026Q2", "2025H1", "2026H1"]
COLS = ["corp_name", "stock_code", "period", "period_type", "period_end", "revenue", "op_income", "net_income",
        "net_income_owner", "assets", "liabilities", "equity", "equity_owner", "interest_expense", "borrowings",
        "sales_growth_yoy", "op_margin", "roa_ann", "roe_ann", "debt_ratio", "icr", "borrow_dep",
        "icr_basis"]


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    df = m03.load_clean()
    ends = df[["stock_code", "period", "period_end"]].drop_duplicates().set_index(["stock_code", "period"])["period_end"]

    frames = []
    for ptype in ["Q", "H1"]:
        w = m03.wide(df, ptype)
        w["period_type"] = ptype
        frames.append(w)
    q = pd.concat(frames, ignore_index=True)
    q = q[q.period.isin(PERIODS)].copy()
    q["period_end"] = [ends.get((s, p), "") for s, p in zip(q.stock_code, q.period)]

    # v2 규칙: 2025Q1 손익은 2026 반기보고서의 '2025 상반기 누적 - 2025 2분기 3개월'로 쓴다.
    # (2026 1분기보고서의 전년 비교 값은 이후 재작성 전 숫자라 2분기·상반기와 기준이 다름 → 같은 반기보고서 기준으로 통일)
    flows = [c for c in ["revenue", "op_income", "net_income", "net_income_owner", "interest_expense", "finance_costs"] if c in q.columns]
    key = q.set_index(["stock_code", "period"])
    for stock in q.stock_code.unique():
        if all((stock, p) in key.index for p in ("2025Q1", "2025Q2", "2025H1")):
            for c in flows:
                h1, q2 = key.loc[(stock, "2025H1"), c], key.loc[(stock, "2025Q2"), c]
                if pd.notna(h1) and pd.notna(q2):
                    q.loc[(q.stock_code == stock) & (q.period == "2025Q1"), c] = h1 - q2

    idx = q.set_index(["stock_code", "period"])
    mult = np.where(q.period_type == "Q", 4, 2)
    base_rev = [idx.revenue.get((s, p.replace("2026", "2025")), np.nan) if p.startswith("2026") else np.nan
                for s, p in zip(q.stock_code, q.period)]
    q["sales_growth_yoy"] = np.where(pd.notna(base_rev) & (np.array(base_rev, dtype=float) != 0),
                                     (q.revenue / np.array(base_rev, dtype=float) - 1) * 100, np.nan)
    q["roa_ann"] = m03.pct(q.net_income * mult, q.assets)
    q["roe_ann"] = m03.pct(q.net_income_owner * mult, q.equity_owner)
    q = m03.finish(q)
    for c in ["sales_growth_yoy", "roa_ann", "roe_ann"]:
        q[c] = pd.to_numeric(q[c]).round(2)

    order = {p: i for i, p in enumerate(PERIODS)}
    q = q.assign(_o=q.period.map(order)).sort_values(["stock_code", "_o"])[COLS]
    q.to_csv(PROC / "quarterly_metrics.csv", index=False, encoding="utf-8-sig")

    print(f"[완료] quarterly_metrics.csv {len(q)}행")
    show = q[["corp_name", "period", "revenue", "op_income", "sales_growth_yoy", "op_margin",
              "roa_ann", "debt_ratio", "icr", "borrow_dep"]].copy()
    show["revenue"] = (show.revenue / 1e8).round(0)
    show["op_income"] = (show.op_income / 1e8).round(0)
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print("(매출·영업이익 단위: 억원)")
        print(show.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
