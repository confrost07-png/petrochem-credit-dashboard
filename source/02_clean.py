"""
02_clean.py : DART 원본 JSON -> 정제 재무 데이터 (긴 형식)

입력 : data/raw/{stock_code}_{year}_{reprt_code}.json (01_collect.py 결과 21건)
출력 : data/processed/financials_clean.csv   정제 금액 (원 단위)
       data/processed/account_mapping.csv    파일별 계정 매핑 결과 (어떤 계정을 어떤 방법으로 찾았는지)
       data/processed/check_log.csv          검산 결과 (stage=02_clean 행만 이 스크립트가 다시 씀)

계정 매핑 원칙
- account_id 우선, 없으면 account_nm(공백 제거 후 완전 일치)으로 찾는다. 수기 입력은 없다.
- 손익은 IS 를 먼저 보고, 없으면 CIS(포괄손익계산서)를 본다.
- 같은 계정이 여러 줄이면 ord(표시 순서)가 가장 앞선 줄을 쓴다.
- 차입금은 표준 ID 우선. 이름은 단기/장기/사채가 명확한 BS 계정만 완전 일치로 허용한다.

기간·금액 컬럼 (1개사 공시 원문 대조 + 3사 숫자 검산으로 확정)
- 사업보고서(11011): thstrm_amount = 당기(연간, 기말), frmtrm_amount = 전기
- 반기보고서(11012): 손익 thstrm_amount = 2분기 3개월, thstrm_add_amount = 상반기 누적,
                     frmtrm_q_amount = 전년 2분기 3개월, frmtrm_add_amount = 전년 상반기 누적
                     재무상태표 thstrm_amount = 6월 말, frmtrm_amount = 전년 말
- 1분기보고서(11013): 손익 thstrm_amount = 1분기, frmtrm_q_amount = 전년 1분기
                     재무상태표 thstrm_amount = 3월 말
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

from company_targets import target_names
TARGETS = target_names()
ANNUAL_YEARS = [2021, 2022, 2023, 2024, 2025]
INTERIM_YEAR = 2026
STAGE = "02_clean"

PL = ["IS", "CIS"]  # 손익 계정을 찾는 순서
BS = ["BS"]

# account_key: (재무제표, account_id 후보, account_nm 후보, 설명)
ACCOUNT_RULES: dict[str, tuple[list[str], list[str], list[str], str]] = {
    "revenue": (PL, ["ifrs-full_Revenue"],
                ["매출액", "매출", "수익(매출액)", "영업수익"], "매출액"),
    "op_income": (PL, ["dart_OperatingIncomeLoss"],
                  ["영업이익", "영업이익(손실)", "영업손실", "영업손익"], "영업이익"),
    "net_income": (PL, ["ifrs-full_ProfitLoss"],
                   ["당기순이익", "당기순이익(손실)", "당기순손실", "반기순이익", "반기순이익(손실)",
                    "반기순손실", "분기순이익", "분기순이익(손실)", "분기순손실"], "연결 당기순이익"),
    "net_income_owner": (PL, ["ifrs-full_ProfitLossAttributableToOwnersOfParent"],
                         ["지배기업의소유주", "지배기업소유주지분", "지배기업의소유주지분",
                          "지배기업의소유주에게귀속되는당기순이익(손실)", "지배기업의소유주에게귀속되는당기순이익"],
                         "지배기업 소유주 귀속 순이익"),
    "net_income_nci": (PL, ["ifrs-full_ProfitLossAttributableToNoncontrollingInterests"],
                       ["비지배지분", "비지배지분에귀속되는당기순이익(손실)", "비지배지분에귀속되는당기순이익"],
                       "비지배지분 귀속 순이익 (검산용)"),
    "interest_expense": (PL, ["ifrs-full_InterestExpense", "dart_InterestExpense", "ifrs-full_InterestExpenseOnBorrowings"],
                         ["이자비용"], "이자비용 (없으면 03 에서 금융원가로 대체)"),
    "finance_costs": (PL, ["ifrs-full_FinanceCosts"], ["금융비용", "금융원가"], "금융원가 (이자비용 대체용)"),
    "assets": (BS, ["ifrs-full_Assets"], ["자산총계"], "자산총계"),
    "liabilities": (BS, ["ifrs-full_Liabilities"], ["부채총계"], "부채총계"),
    "equity": (BS, ["ifrs-full_Equity"], ["자본총계"], "자본총계"),
    "equity_owner": (BS, ["ifrs-full_EquityAttributableToOwnersOfParent"],
                     ["지배기업의소유주지분", "지배기업소유주지분", "지배기업의소유주에게귀속되는자본"],
                     "지배기업 소유주지분"),
    # 차입금: account_id 로만 찾는다
    "borrow_current": (BS, ["ifrs-full_ShorttermBorrowings", "dart_ShortTermBorrowings",
                            "dart_CurrentLoansReceived", "dart_CurrentSecuredBankLoansReceived", "dart_CurrentUnsecuredBankLoansReceived",
                            "ifrs-full_CurrentLoansReceivedAndCurrentPortionOfNoncurrentLoansReceived",
                            "ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"],
                       ["단기차입금","단기차입부채","유동차입금","유동차입부채","단기이자부차입금","단기차입금및사채"],
                       "유동 차입금 (단기차입금, 회사에 따라 유동성장기부채·사채 포함)"),
    "borrow_current_lt": (BS, ["ifrs-full_CurrentPortionOfLongtermBorrowings", "dart_CurrentPortionOfLongTermBorrowings",
                               "ifrs-full_CurrentPortionOfNoncurrentLoansReceived",
                               "ifrs-full_OtherCurrentBorrowingsAndCurrentPortionOfOtherNoncurrentBorrowings"],
                          ["유동성장기차입금","유동성장기부채","유동성장기차입부채","유동성이자부차입금","유동성장기차입금및사채"],
                          "유동성장기부채 (별도 줄이 있을 때만)"),
    "borrow_noncurrent": (BS, ["ifrs-full_LongtermBorrowings", "dart_LongTermBorrowingsGross",
                               "ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived", "dart_NoncurrentLoansReceived", "ifrs-full_LoansReceived",
                               "ifrs-full_NoncurrentPortionOfNoncurrentBorrowings"],
                          ["장기차입금","장기차입부채","비유동차입금","비유동성장기차입금","장기차입금및사채","사채및장기차입금"],
                          "비유동 차입금 (장기차입금, 회사에 따라 사채 포함)"),
    "bonds": (BS, ["dart_BondsIssued", "ifrs-full_BondsIssued", "ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued"], ["사채","비유동사채"],
              "사채 (별도 줄이 있을 때만)"),
    "borrow_current_bonds": (BS, ["ifrs-full_CurrentBondsIssuedAndCurrentPortionOfNoncurrentBondsIssued",
                                   "dart_CurrentBondsIssued", "dart_CurrentPortionOfBonds", "ifrs-full_CurrentPortionOfBondsIssued"],
                             ["유동성사채","단기사채"],
                             "유동 사채 (차입금 합계에 포함되지 않은 별도 계정)"),
    "borrow_convertible": (BS,["dart_ConvertibleBondsNet"],["전환사채","전환사채,순액"],"전환사채 장부금액"),
    "borrow_exchangeable": (BS,["dart_ExchangeableBondsNet"],["교환사채","교환사채,순액"],"교환사채 장부금액"),
}
PL_KEYS = [k for k, v in ACCOUNT_RULES.items() if v[0] is PL]
BS_KEYS = [k for k, v in ACCOUNT_RULES.items() if v[0] is BS]

CLEAN_COLS = ["corp_name", "stock_code", "period", "period_type", "account_key", "account_id",
              "account_nm", "value_krw", "rcept_no",
              # 추적용 추가 컬럼
              "period_end", "sj_div", "reprt_code", "amount_col", "source_file", "fs_div"]
CHECK_COLS = ["stage", "check", "corp_name", "stock_code", "period", "item",
              "expected", "actual", "diff", "result", "note"]


# ---------------------------------------------------------------------------
# 도구
# ---------------------------------------------------------------------------
def to_number(v: object) -> int | None:
    """쉼표·공백·'-' 처리. 빈 값은 None (0 으로 채우지 않는다)."""
    if v is None:
        return None
    s = str(v).replace(",", "").replace(" ", "").strip()
    if s in ("", "-"):
        return None
    neg = s.startswith("(") and s.endswith(")")  # (1,000) 표기 대비
    s = s.strip("()")
    try:
        n = int(float(s))
    except ValueError:
        return None
    return -n if neg else n


def norm(name: object) -> str:
    return str(name or "").replace(" ", "").strip()


def load_rows(stock: str, year: int, reprt: str) -> tuple[list[dict], str]:
    path = RAW_DIR / f"{stock}_{year}_{reprt}.json"
    if not path.exists():
        return [], path.name
    data = json.loads(path.read_text(encoding="utf-8"))
    if str(data.get("status")) != "000":
        return [], path.name
    rows=data.get("list") or []
    basis=data.get('_collection',{}).get('fs_div')
    if basis:
        rows=[{**r,'fs_div':basis} for r in rows]
    return rows, path.name


def find_account(rows: list[dict], key: str) -> tuple[dict | None, str]:
    sj_divs, ids, names, _ = ACCOUNT_RULES[key]
    names_n = [norm(n) for n in names]
    for sj in sj_divs:  # IS 먼저, 없으면 CIS
        cand = sorted([r for r in rows if r.get("sj_div") == sj], key=lambda r: int(r.get("ord") or 9999))
        for code in ids:
            for r in cand:
                if key=='borrow_current' and norm(r.get('account_nm')) in ('유동성장기부채','유동성장기차입금','유동성장기차입부채'):
                    continue
                if r.get("account_id") == code:
                    return r, "account_id"
        for r in cand:
            if key=='bonds' and r.get('account_id')=='dart_BondsIssuedNominalValue':
                continue
            if names_n and norm(r.get("account_nm")) in names_n:
                return r, "account_nm"
    return None, "not_found"


# ---------------------------------------------------------------------------
# 보고서별 추출 설정: (period, period_type, period_end, 손익 금액 컬럼, 재무상태표 금액 컬럼)
# ---------------------------------------------------------------------------
def extraction_plan(year: int, reprt: str) -> list[tuple[str, str, str, list[str] | None, str | None]]:
    if reprt == "11011":
        return [
            (str(year), "FY", f"{year}-12-31", ["thstrm_amount"], "thstrm_amount"),
            # 전기 금액: 2021 보고서의 2020 값(성장률·평균 잔액용)과 재작성 여부 검산용
            (str(year - 1), "FY_PRIOR", f"{year - 1}-12-31", ["frmtrm_amount"], "frmtrm_amount"),
        ]
    if reprt == "11012":
        return [
            (f"{year}H1", "H1", f"{year}-06-30", ["thstrm_add_amount"], "thstrm_amount"),
            (f"{year - 1}H1", "H1", f"{year - 1}-06-30", ["frmtrm_add_amount"], None),
            (f"{year}Q2", "Q", f"{year}-06-30", ["thstrm_amount"], "thstrm_amount"),
            (f"{year - 1}Q2", "Q", f"{year - 1}-06-30", ["frmtrm_q_amount"], None),
        ]
    if reprt == "11013":
        return [
            (f"{year}Q1", "Q", f"{year}-03-31", ["thstrm_amount"], "thstrm_amount"),
            (f"{year - 1}Q1", "Q", f"{year - 1}-03-31", ["frmtrm_q_amount", "frmtrm_add_amount"], None),
        ]
    raise ValueError(reprt)


# ---------------------------------------------------------------------------
# 정제
# ---------------------------------------------------------------------------
def clean() -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    records: list[dict] = []
    mapping: list[dict] = []
    checks: list[dict] = []

    jobs = [(s, y, "11011") for s in TARGETS for y in ANNUAL_YEARS]
    jobs += [(s, INTERIM_YEAR, r) for s in TARGETS for r in ("11012", "11013")]

    for stock, year, reprt in jobs:
        corp = TARGETS[stock]
        rows, fname = load_rows(stock, year, reprt)
        if not rows:
            continue

        rcepts = sorted({r.get("rcept_no", "") for r in rows})
        if len(rcepts) != 1:
            checks.append(chk("rcept_no 단일", corp, stock, f"{year}_{reprt}", "rcept_no",
                              1, len(rcepts), None, "WARN", f"한 파일에 접수번호가 여러 개: {rcepts}"))
        rcept_no = rcepts[-1]  # 최신 접수번호

        found = {k: find_account(rows, k) for k in ACCOUNT_RULES}
        # 별도 단기차입금 + 유동성 대체 계정이 함께 표시되는 예외는
        # 다른 유동부채 항목과 합산해 유동부채 총계가 정확히 맞을 때만 분리한다.
        short=found['borrow_current'][0]
        agg=next((a for a in rows if a.get('sj_div')=='BS' and a.get('account_id')=='ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings'),None)
        other_ids={'ifrs-full_CurrentLeaseLiabilities','ifrs-full_CurrentTaxLiabilities',
                   'ifrs-full_OtherCurrentFinancialLiabilities','ifrs-full_OtherCurrentLiabilities',
                   'ifrs-full_TradeAndOtherCurrentPayables','ifrs-full_CurrentProvisions',
                   'dart_CurrentDerivativeLiabilities'}
        total=next((a for a in rows if a.get('sj_div')=='BS' and a.get('account_id')=='ifrs-full_CurrentLiabilities'),None)
        if short and agg and short is not agg and found['borrow_current_lt'][0] is None and total:
            leaves=[short,agg]+[a for a in rows if a.get('sj_div')=='BS' and a.get('account_id') in other_ids]
            values=[to_number(a.get('thstrm_amount')) for a in leaves]
            amount=to_number(total.get('thstrm_amount'))
            if amount is not None and all(v is not None for v in values) and abs(sum(values)-amount)<=1:
                found['borrow_current_lt']=(agg,'current_liabilities_reconciled_split')
        basis = rows[0].get('fs_div','CFS')
        if basis == 'OFS':
            found['net_income_owner'] = (found['net_income'][0], 'OFS_same_as_net')
            found['equity_owner'] = (found['equity'][0], 'OFS_same_as_equity')
        # 이미 유동차입금 전체에 유동성 장기부채가 포함된 경우 중복 합산하지 않는다.
        bc=found['borrow_current'][0]
        if bc and bc.get('account_id') in ('ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings',
                                          'ifrs-full_CurrentLoansReceivedAndCurrentPortionOfNoncurrentLoansReceived'):
            found['borrow_current_lt']=(found['borrow_current_lt'][0],'included_in_current_total')
        if bc and (bc.get('account_id')=='ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings' or '사채' in bc.get('account_nm','')):
            found['borrow_current_bonds']=(found['borrow_current_bonds'][0],'included_in_current_total')
        bn=found['borrow_noncurrent'][0]
        if bn and '사채' in bn.get('account_nm','') and '차입' in bn.get('account_nm',''):
            found['bonds']=(found['bonds'][0],'included_in_noncurrent_total')
        bl=found['borrow_current_lt'][0]
        if bl and '사채' in bl.get('account_nm',''):
            found['borrow_current_bonds']=(found['borrow_current_bonds'][0],'included_in_current_lt_total')
        seen=set()
        for key in ('borrow_current','borrow_current_lt','borrow_noncurrent','bonds','borrow_current_bonds','borrow_convertible','borrow_exchangeable'):
            row,how=found[key]
            if row is None or how.startswith('included_in_'):continue
            if id(row) in seen:found[key]=(row,'included_in_same_source_row')
            else:seen.add(id(row))
        for key, (row, how) in found.items():
            mapping.append({
                "corp_name": corp, "stock_code": stock, "bsns_year": year, "reprt_code": reprt,
                "account_key": key, "description": ACCOUNT_RULES[key][3], "match_method": how,
                "sj_div": row.get("sj_div") if row else "", "account_id": row.get("account_id") if row else "",
                "account_nm": row.get("account_nm") if row else "", "rcept_no": rcept_no, "source_file": fname,
            })

        for period, ptype, pend, pl_cols, bs_col in extraction_plan(year, reprt):
            for key, (row, how) in found.items():
                if row is None or how.startswith('included_in_'):
                    continue
                is_pl = key in PL_KEYS
                if is_pl:
                    cols = pl_cols
                elif bs_col:
                    cols = [bs_col]
                else:
                    continue  # 전년 반기·분기 말 재무상태표는 보고서에 없음
                value, used = None, cols[0]
                for c in cols:
                    if c in row and to_number(row.get(c)) is not None:
                        value, used = to_number(row.get(c)), c
                        break
                records.append({
                    "corp_name": corp, "stock_code": stock, "period": period, "period_type": ptype,
                    "account_key": key, "account_id": row.get("account_id"), "account_nm": row.get("account_nm"),
                    "value_krw": value, "rcept_no": rcept_no, "period_end": pend, "sj_div": row.get("sj_div"),
                    "reprt_code": reprt, "amount_col": used, "source_file": fname, "fs_div": basis,
                })

        # 2분기 단독 검산: 반기보고서 3개월 금액 = 반기 누적 - 1분기
        if reprt == "11012":
            q1_rows, _ = load_rows(stock, year, "11013")
            for key in ["revenue", "op_income", "net_income", "net_income_owner", "finance_costs"]:
                h, _ = found[key]
                q, _ = find_account(q1_rows, key)
                if not h or not q:
                    continue
                for label, direct, cum, q1 in [
                    (f"{year}Q2", h.get("thstrm_amount"), h.get("thstrm_add_amount"), q.get("thstrm_amount")),
                    (f"{year - 1}Q2", h.get("frmtrm_q_amount"), h.get("frmtrm_add_amount"), q.get("frmtrm_q_amount")),
                ]:
                    d, c, a = to_number(direct), to_number(cum), to_number(q1)
                    if None in (d, c, a):
                        continue
                    diff = d - (c - a)
                    note = "반기보고서 3개월 금액 vs (반기 누적 - 1분기보고서 1분기)"
                    if diff != 0 and label.startswith(str(year - 1)):
                        note += ". 전년 비교 수치가 두 보고서에서 다르게 표시됨 (재작성 가능성, 원문 확인 필요)"
                    checks.append(chk("2분기 단독 대조", corp, stock, label, key, c - a, d, diff,
                                      "OK" if diff == 0 else "WARN", note))

            # 반기보고서의 전년 말 재무상태표 = 2025 사업보고서 기말
            fy_rows, _ = load_rows(stock, year - 1, "11011")
            for key in ["assets", "liabilities", "equity"]:
                h, _ = found[key]
                f, _ = find_account(fy_rows, key)
                if h and f:
                    a, b = to_number(f.get("thstrm_amount")), to_number(h.get("frmtrm_amount"))
                    if None not in (a, b):
                        checks.append(chk("전년 말 잔액 대조", corp, stock, f"{year - 1}", key, a, b, b - a,
                                          "OK" if a == b else "WARN", "반기보고서 전기말 vs 사업보고서 기말"))

    df = pd.DataFrame(records, columns=CLEAN_COLS)
    df["value_krw"] = df["value_krw"].astype("Int64")
    order = {"FY": 0, "FY_PRIOR": 1, "H1": 2, "Q": 3}
    df = df.assign(_o=df["period_type"].map(order)).sort_values(
        ["stock_code", "_o", "period", "account_key"]).drop(columns="_o")
    return df, pd.DataFrame(mapping), checks


def _int_or_blank(v: object) -> object:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return ""
    return int(v)


def chk(check, corp, stock, period, item, expected, actual, diff, result, note) -> dict:
    return {"stage": STAGE, "check": check, "corp_name": corp, "stock_code": stock, "period": period,
            "item": item, "expected": _int_or_blank(expected), "actual": _int_or_blank(actual),
            "diff": _int_or_blank(diff), "result": result, "note": note}


def restatement_checks(df: pd.DataFrame) -> list[dict]:
    """사업보고서 Y 의 전기 금액(FY_PRIOR) vs 사업보고서 Y-1 의 당기 금액(FY). 다르면 재작성 표시."""
    out = []
    fy = df[df.period_type == "FY"].set_index(["stock_code", "period", "account_key"])["value_krw"]
    pr = df[df.period_type == "FY_PRIOR"]
    for _, r in pr.iterrows():
        k = (r.stock_code, r.period, r.account_key)
        if k not in fy.index or pd.isna(r.value_krw) or pd.isna(fy[k]):
            continue
        a, b = int(fy[k]), int(r.value_krw)
        if a != b:
            out.append(chk("전기 재작성 여부", r.corp_name, r.stock_code, r.period, r.account_key, a, b, b - a,
                           "INFO", f"{int(r.period) + 1} 사업보고서의 전기 금액이 {r.period} 사업보고서 당기 금액과 다름. "
                                   "지표는 각 연도 사업보고서 당기 금액을 사용"))
    return out


def missing_checks(mapping: pd.DataFrame) -> list[dict]:
    out = []
    for _, r in mapping[mapping.match_method == "not_found"].iterrows():
        key = r.account_key
        # 별도 줄이 없는 게 정상인 계정은 INFO 로만 남긴다
        level = "INFO" if key in ("interest_expense", "borrow_current_lt", "bonds", "net_income_nci") else "WARN"
        out.append(chk("계정 매핑", r.corp_name, r.stock_code, f"{r.bsns_year}_{r.reprt_code}", key,
                       None, None, None, level, f"{ACCOUNT_RULES[key][3]} 계정을 찾지 못함"))
    return out


def write_check_log(rows: list[dict]) -> pd.DataFrame:
    path = OUT_DIR / "check_log.csv"
    new = pd.DataFrame(rows, columns=CHECK_COLS)
    if path.exists():
        old = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        old = old[old["stage"] != STAGE]  # 이 스크립트의 이전 결과만 지우고 다시 쓴다
        new = pd.concat([old, new.astype(str)], ignore_index=True)
    new.to_csv(path, index=False, encoding="utf-8-sig")
    return new


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df, mapping, checks = clean()
    checks += restatement_checks(df)
    checks += missing_checks(mapping)

    df.to_csv(OUT_DIR / "financials_clean.csv", index=False, encoding="utf-8-sig")
    mapping.to_csv(OUT_DIR / "account_mapping.csv", index=False, encoding="utf-8-sig")
    write_check_log(checks)

    by_method = mapping.match_method.value_counts().to_dict()
    print(f"[완료] financials_clean.csv {len(df)}행 (빈 금액 {int(df.value_krw.isna().sum())}건)")
    print(f"[완료] account_mapping.csv {len(mapping)}행, 매핑 방법별: {by_method}")
    print("[완료] 수기 입력: 0건")
    name_hits = mapping[mapping.match_method == "account_nm"]
    if len(name_hits):
        print("\n[참고] account_id 가 표준 코드가 아니어서 계정명으로 찾은 계정:")
        for _, r in name_hits.iterrows():
            print(f"  {r.corp_name} {r.bsns_year}_{r.reprt_code} {r.account_key:<18} <- '{r.account_nm}' ({r.account_id})")

    ck = pd.DataFrame(checks, columns=CHECK_COLS)
    print("\n[검산] 결과별 건수:", ck.result.value_counts().to_dict() if len(ck) else {})
    warns = ck[ck.result == "WARN"]
    for _, r in warns.iterrows():
        print(f"  WARN {r['check']} | {r['corp_name']} {r['period']} {r['item']} | 기대 {r['expected']} 실제 {r['actual']} 차이 {r['diff']}")
        print(f"       {r['note']}")
    print("  자세한 내용: data/processed/check_log.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
