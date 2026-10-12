"""팀 데이터 파이프라인의 검산 기록을 앱·보고서용 Q2 대조표로 정리한다."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"


def main() -> None:
    checks = pd.read_csv(DATA / "check_log.csv", dtype={"stock_code": str})
    rows = checks[checks.check == "2분기 단독 대조"].copy()
    output = rows.rename(columns={"item": "field", "actual": "reported_3month",
                                  "expected": "halfyear_less_q1", "diff": "difference",
                                  "result": "status"})[
        ["stock_code", "corp_name", "period", "field", "reported_3month",
         "halfyear_less_q1", "difference", "status"]
    ]
    output["status"] = output.status.map({"OK": "MATCH", "WARN": "DIFFERENCE"})
    if output.status.isna().any():
        raise ValueError("검산 결과에 알 수 없는 상태가 있습니다.")
    output["selected_method"] = "반기보고서에 표시된 3개월 금액"
    output.to_csv(DATA / "q2_reconciliation.csv", index=False, encoding="utf-8-sig")
    print(f"Q2 대조 {len(output)}건 저장, 차이 {(output.status == 'DIFFERENCE').sum()}건")


if __name__ == "__main__":
    main()
