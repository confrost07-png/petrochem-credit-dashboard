"""실제 데이터의 구조와 계산을 검증한다. 샘플 데이터는 통과시키지 않는다."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
EXPECTED = ["2021", "2022", "2023", "2024", "2025", "2026H1"]


def main() -> None:
    if (DATA / ".sample_data").exists():
        raise SystemExit("개발용 샘플입니다. 실제 DART 수집 후 다시 검사해 주세요.")
    metrics = pd.read_csv(DATA / "metrics.csv", dtype={"stock_code": str, "period": str})
    quarterly = pd.read_csv(DATA / "quarterly_metrics.csv", dtype={"stock_code": str, "period": str})
    mapping = pd.read_csv(DATA / "account_mapping.csv", dtype={"stock_code": str})
    reconciliation = pd.read_csv(DATA / "q2_reconciliation.csv")
    if metrics.duplicated(["stock_code", "period"]).any() or quarterly.duplicated(["stock_code", "period"]).any():
        raise ValueError("기업-기간 중복")
    for stock in ["011170", "006650", "011780"]:
        actual = set(metrics[metrics.stock_code == stock].period)
        if actual != set(EXPECTED):
            raise ValueError(f"{stock} 기간 누락: {set(EXPECTED) - actual}")
    baseline=metrics[metrics.stock_code.isin(["011170","006650","011780"])]
    for field in ["revenue", "op_income", "net_income", "assets", "liabilities", "equity"]:
        if baseline[field].isna().any():
            rows = baseline[baseline[field].isna()][["stock_code", "period"]].values.tolist()
            raise ValueError(f"필수 계정 {field} 누락: {rows}")
    complete=metrics.dropna(subset=['assets','liabilities','equity'])
    tolerance=pd.to_numeric(complete.get('balance_tolerance',pd.Series(1,index=complete.index)),errors='coerce').fillna(1)
    if not ((complete.assets - (complete.liabilities + complete.equity)).abs() <= tolerance).all():
        raise ValueError("자산 = 부채 + 자본 검증 실패")
    check = (metrics.op_income / metrics.revenue * 100 - metrics.op_margin).abs()
    if (check > .02).any():
        raise ValueError("영업이익률 재계산 불일치")
    check = (metrics.liabilities / metrics.equity * 100 - metrics.debt_ratio).abs()
    if (check > .02).any():
        raise ValueError("부채비율 재계산 불일치")
    check = (metrics.borrowings / metrics.assets * 100 - metrics.borrow_dep).abs()
    if (check > .02).any():
        raise ValueError("차입금 의존도 재계산 불일치")
    if not set(reconciliation.status).issubset({"MATCH", "DIFFERENCE"}):
        raise ValueError("Q2 대조 결과 형식 오류")
    missing = mapping[mapping.match_method == "not_found"]
    differences = reconciliation[reconciliation.status == "DIFFERENCE"]
    quality=pd.read_csv(DATA/'data_quality.csv',dtype={'stock_code':str,'period':str})
    ready=quality[quality.management_ready=='Y']
    if len(quality)!=len(metrics) or quality.duplicated(['stock_code','period']).any():
        raise ValueError('기업·기간 품질표 누락 또는 중복')
    for _,r in ready.iterrows():
        hit=metrics[(metrics.stock_code==r.stock_code)&(metrics.period==r.period)].iloc[0]
        if hit[['icr','borrow_dep','equity']].isna().any() or hit.equity<=0:
            raise ValueError('판정 가능 행에 누락 지표 또는 자본 이상 존재')
    print(f"검증 통과: 재무 데이터 {metrics.corp_name.nunique()}개 기업, 지표 {len(metrics)}행, 분기 {len(quarterly)}행. 원본 계정 미매핑 {len(missing)}건, Q2 대조 차이 {len(differences)}건.")
    if not missing.empty:
        print("원본 계정 미매핑과 대체 방법은 data/processed/account_mapping.csv를 확인하세요.")
    if not differences.empty:
        print("공시 간 금액 차이는 data/processed/q2_reconciliation.csv를 확인하세요.")


if __name__ == "__main__":
    main()
