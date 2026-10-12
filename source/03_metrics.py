"""
03_metrics.py : 본 분석용 공통 지표 (팀 공통 수치 기준)

입력 : data/processed/financials_clean.csv
출력 : data/processed/metrics.csv   (2021~2025 FY + 2026H1, 분기 행 없음)
       data/processed/check_log.csv (stage=03_metrics 행만 이 스크립트가 다시 씀)

산식 (원 단위로 계산, 비율은 소수 둘째 자리 반올림)
  매출 성장률   = (당기 매출 / 전기 매출 - 1) x 100
  영업이익률    = 영업이익 / 매출 x 100
  ROA          = 연결 당기순이익 / 평균 총자산 x 100
  ROE          = 지배 순이익 / 평균 지배기업 소유주지분 x 100
  부채비율      = 기말 부채총계 / 기말 자본총계 x 100
  이자보상배율  = 영업이익 / 이자비용 (이자비용 계정이 없으면 금융원가, icr_basis 에 표시)
  차입금 의존도 = 차입금 합계 / 자산총계 x 100
  평균 잔액     = (기초 + 기말) / 2
  2021 의 전기(2020) 값은 2021 사업보고서의 전기 금액을 쓴다.
  2026H1: 매출 성장률은 2025 상반기 대비, ROA·ROE 는 순이익 x 2 (연환산) / 6월 말 잔액, annualized=Y
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
STAGE = "03_metrics"

# 전기 금액 기준
#  "previous_report": 2022 이후는 직전 연도 사업보고서의 당기 금액 (2021 만 2021 보고서 전기 금액) <- 기본
#  "restated"       : 같은 사업보고서의 전기 금액(재작성 반영). 비어 있으면 직전 연도 보고서 값으로 대체
PRIOR_BASIS = "restated"   # v2: 각 연도 보고서에 실린 재작성 전기 값 사용

FY_YEARS = [2021, 2022, 2023, 2024, 2025]
BORROW_PARTS = ["borrow_current", "borrow_current_lt", "borrow_noncurrent", "bonds", "borrow_current_bonds", "borrow_convertible", "borrow_exchangeable"]
METRIC_COLS = ["corp_name", "stock_code", "period", "period_type", "revenue", "op_income", "net_income",
               "net_income_owner", "assets", "liabilities", "equity", "equity_owner", "interest_expense",
               "borrowings", "sales_growth", "op_margin", "roa", "roe", "debt_ratio", "icr", "borrow_dep",
               "annualized", "icr_basis", "fs_div", "roe_basis"]
CHECK_COLS = ["stage", "check", "corp_name", "stock_code", "period", "item",
              "expected", "actual", "diff", "result", "note"]


def load_clean() -> pd.DataFrame:
    path = PROC / "financials_clean.csv"
    if not path.exists():
        sys.exit("[중단] financials_clean.csv 가 없습니다. 02_clean.py 를 먼저 실행하세요.")
    df = pd.read_csv(path, dtype={"stock_code": str, "period": str, "rcept_no": str}, encoding="utf-8-sig")
    df["value_krw"] = pd.to_numeric(df["value_krw"], errors="coerce")
    return df


def wide(df: pd.DataFrame, period_type: str) -> pd.DataFrame:
    """(stock_code, period) x account_key 표. 차입금 합계와 이자비용 대체도 여기서 만든다."""
    sub = df[df.period_type == period_type]
    w = sub.pivot_table(index=["corp_name", "stock_code", "period"], columns="account_key",
                        values="value_krw", aggfunc="first")
    for c in set(BORROW_PARTS + ["interest_expense", "finance_costs", "net_income_nci", "revenue", "op_income", "net_income", "net_income_owner", "assets", "liabilities", "equity", "equity_owner"]) - set(w.columns):
        w[c] = np.nan
    parts = w[[c for c in BORROW_PARTS if c in w.columns]]
    w["borrowings"] = parts.sum(axis=1, min_count=1)  # 전부 비면 NaN (0 으로 채우지 않음)
    has_int = w["interest_expense"].notna()
    w["icr_basis"] = np.where(has_int, "이자비용", np.where(w["finance_costs"].notna(), "금융원가", ""))
    w["interest_expense"] = w["interest_expense"].where(has_int, w["finance_costs"])
    w=w.reset_index()
    basis=sub.groupby(['stock_code','period']).fs_div.first().to_dict() if 'fs_div' in sub.columns else {}
    w['fs_div']=[basis.get((r.stock_code,r.period),'CFS') for _,r in w.iterrows()]
    w['roe_basis']=np.where(w.fs_div=='OFS','별도 순이익/자본','지배 순이익/지배 자본')
    return w


def pct(a, b):
    return np.where((b != 0) & pd.notna(a) & pd.notna(b), a / b * 100, np.nan)


def ratio(a, b):
    return np.where((b != 0) & pd.notna(a) & pd.notna(b), a / b, np.nan)


def finish(m: pd.DataFrame) -> pd.DataFrame:
    m["op_margin"] = pct(m.op_income, m.revenue)
    m["debt_ratio"] = pct(m.liabilities, m.equity.where(m.equity>0))
    m["icr"] = ratio(m.op_income, m.interest_expense.where(m.interest_expense>0))
    m["borrow_dep"] = pct(m.borrowings, m.assets)
    for c in ["sales_growth", "op_margin", "roa", "roe", "debt_ratio", "icr", "borrow_dep"]:
        if c in m.columns:
            m[c] = pd.to_numeric(m[c]).round(2)
    money = ["revenue", "op_income", "net_income", "net_income_owner", "assets", "liabilities",
             "equity", "equity_owner", "interest_expense", "borrowings"]
    m[money] = m[money].astype("Int64")
    return m


def annual(df: pd.DataFrame) -> pd.DataFrame:
    fy = wide(df, "FY")
    prior = wide(df, "FY_PRIOR").set_index(["stock_code", "period"])
    fy_idx = fy.set_index(["stock_code", "period"])

    def prev(stock: str, year: int, col: str):
        p = str(year - 1)
        if (stock,p) in fy_idx.index and fy_idx.loc[(stock,p),'fs_div'] != fy_idx.loc[(stock,str(year)),'fs_div']:
            return np.nan  # 연결/별도 기준이 바뀌면 성장률·평균잔액을 혼합하지 않는다.
        if year == FY_YEARS[0] or PRIOR_BASIS == "restated":
            v = prior[col].get((stock, p), np.nan) if col in prior.columns else np.nan
            if pd.notna(v) or year == FY_YEARS[0]:
                return v
        return fy_idx[col].get((stock, p), np.nan)

    rows = []
    for _, r in fy.iterrows():
        y = int(r.period)
        if y not in FY_YEARS:
            continue
        rev0, a0, e0 = prev(r.stock_code, y, "revenue"), prev(r.stock_code, y, "assets"), prev(r.stock_code, y, "equity_owner")
        d = r.to_dict()
        d["period_type"] = "FY"
        d["annualized"] = "N"
        d["sales_growth"] = (r.revenue / rev0 - 1) * 100 if pd.notna(rev0) and rev0 else np.nan
        d["roa"] = r.net_income / ((a0 + r.assets) / 2) * 100 if pd.notna(a0) and (a0+r.assets)>0 else np.nan
        d["roe"] = r.net_income_owner / ((e0 + r.equity_owner) / 2) * 100 if pd.notna(e0) and e0>0 and r.equity_owner>0 else np.nan
        rows.append(d)
    return finish(pd.DataFrame(rows))


def half(df: pd.DataFrame) -> pd.DataFrame:
    h = wide(df, "H1").set_index(["stock_code", "period"])
    rows = []
    for (stock, period), r in h.iterrows():
        if period != "2026H1":
            continue
        base = h.loc[(stock, "2025H1")] if (stock, "2025H1") in h.index else None
        d = r.to_dict()
        d.update(stock_code=stock, period=period, period_type="H1", annualized="Y")
        d["sales_growth"] = (r.revenue / base.revenue - 1) * 100 if base is not None and base.revenue else np.nan
        d["roa"] = r.net_income * 2 / r.assets * 100 if r.assets else np.nan
        d["roe"] = r.net_income_owner * 2 / r.equity_owner * 100 if r.equity_owner>0 else np.nan
        rows.append(d)
    return finish(pd.DataFrame(rows))


def checks(df: pd.DataFrame) -> list[dict]:
    out = []
    for ptype in ["FY", "FY_PRIOR", "H1", "Q"]:
        w = wide(df, ptype)
        for _, r in w.iterrows():
            if pd.notna(r.get("assets")) and pd.notna(r.get("liabilities")) and pd.notna(r.get("equity")):
                diff = r.assets - (r.liabilities + r.equity)
                out.append(row("자산 = 부채 + 자본", r, ptype, "assets", r.liabilities + r.equity, r.assets, diff,
                               "OK" if diff == 0 else "WARN", ""))
            if pd.notna(r.get("net_income")) and pd.notna(r.get("net_income_owner")):
                nci = r.get("net_income_nci")
                if pd.isna(nci):
                    diff = r.net_income_owner - r.net_income
                    out.append(row("지배 + 비지배 = 연결 순이익", r, ptype, "net_income", r.net_income,
                                   r.net_income_owner, diff, "OK" if diff == 0 else "WARN",
                                   "비지배 순이익 계정 없음(또는 빈 값): 지배 = 연결 이면 통과"))
                else:
                    diff = r.net_income_owner + nci - r.net_income
                    out.append(row("지배 + 비지배 = 연결 순이익", r, ptype, "net_income", r.net_income,
                                   r.net_income_owner + nci, diff, "OK" if diff == 0 else "WARN", ""))
    return out


def row(check, r, ptype, item, expected, actual, diff, result, note) -> dict:
    f = lambda v: "" if pd.isna(v) else int(v)
    return {"stage": STAGE, "check": check, "corp_name": r.corp_name, "stock_code": r.stock_code,
            "period": f"{r.period}({ptype})", "item": item, "expected": f(expected), "actual": f(actual),
            "diff": f(diff), "result": result, "note": note}


def write_check_log(rows: list[dict]) -> None:
    path = PROC / "check_log.csv"
    new = pd.DataFrame(rows, columns=CHECK_COLS).astype(str)
    if path.exists():
        old = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
        new = pd.concat([old[old["stage"] != STAGE], new], ignore_index=True)
    new.to_csv(path, index=False, encoding="utf-8-sig")


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    df = load_clean()
    m = pd.concat([annual(df), half(df)], ignore_index=True)
    m = m.sort_values(["stock_code", "period"])[METRIC_COLS]
    m.to_csv(PROC / "metrics.csv", index=False, encoding="utf-8-sig")

    ck = checks(df)
    write_check_log(ck)
    ckdf = pd.DataFrame(ck)
    print(f"[완료] metrics.csv {len(m)}행 (전기 기준: {PRIOR_BASIS})")
    print(f"[완료] 이자비용 출처: {m.icr_basis.value_counts().to_dict()}")
    print("[검산]", ckdf.result.value_counts().to_dict())
    for _, r in ckdf[ckdf.result == "WARN"].iterrows():
        print(f"  WARN {r['check']} | {r['corp_name']} {r['period']} | 차이 {r['diff']} 원 | {r['note']}")
    show = m[["corp_name", "period", "sales_growth", "op_margin", "roa", "roe", "debt_ratio", "icr", "borrow_dep"]]
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(show.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
