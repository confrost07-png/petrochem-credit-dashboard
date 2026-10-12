"""실데이터와 필수 결과물 점검 후 제출 ZIP을 생성한다."""

import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md", "requirements.txt", ".env.example", "TROUBLESHOOTING.md",
    "data/raw/corp_codes.csv", "data/raw/collect_log.csv", "data/processed/metrics.csv",
    "data/processed/quarterly_metrics.csv", "data/processed/account_mapping.csv",
    "data/processed/financials_clean.csv", "data/processed/company_comparison.csv",
    "data/processed/check_log.csv", "data/processed/q2_reconciliation.csv",
    "data/processed/events.csv", "app/app.py", "output/streamlit_screen.png",
    "app/candidates/app_minji.py", "app/credit_logic.py", "app/credit_ui.py",
    "data/processed/company_registry.csv", "data/processed/collection_coverage.csv", "data/processed/data_quality.csv",
    "report/분석결과_요약보고서.pdf",
]
EXCLUDE_PARTS = {".env", ".venv", ".runtime", ".deck_work", "node_modules", "__pycache__", ".git", "streamlit_full.png"}


def main() -> None:
    if (ROOT / "data" / "processed" / ".sample_data").exists():
        raise SystemExit("가상 데이터가 남아 있어 제출 ZIP을 만들 수 없습니다.")
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    raw = list((ROOT / "data" / "raw").glob("*.json"))
    charts = list((ROOT / "output" / "charts").glob("*.png"))
    if len(raw) < 21:
        missing.append(f"기존 검증 원본 JSON 21개 이상 (현재 {len(raw)}개)")
    if len(charts) < 5:
        missing.append(f"차트 PNG 5개 이상 (현재 {len(charts)}개)")
    if missing:
        raise SystemExit("제출 결과물 누락:\n- " + "\n- ".join(missing))
    out = ROOT.parent / f"{ROOT.name}_사이트시연.zip"
    from dotenv import dotenv_values
    private=[v.encode() for k,v in dotenv_values(ROOT/'.env',encoding='utf-8-sig').items()
             if k.endswith('_API_KEY') and v and len(v)>=20 and v!='YOUR_API_KEY']
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for directory, dirs, files in os.walk(ROOT, followlinks=False):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_PARTS and not d.startswith(".chart-data-")
                       and not (Path(directory) / d).is_junction()]
            for filename in files:
                if filename in EXCLUDE_PARTS:
                    continue
                path = Path(directory) / filename
                if any(key in path.read_bytes() for key in private):
                    raise SystemExit('비공개 키가 포함된 파일 발견: '+str(path.relative_to(ROOT)))
                archive.write(path, arcname=f"{ROOT.name}/{path.relative_to(ROOT).as_posix()}")
    print(out)


if __name__ == "__main__":
    main()
