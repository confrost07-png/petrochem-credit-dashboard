"""
01_collect.py : DART 재무제표 원본 수집 (석유화학 3사)

- .env 의 DART_API_KEY 를 python-dotenv 로 읽는다. 키 값은 화면·로그·오류 문구에 남기지 않는다.
- corpCode.xml(ZIP)에서 3사의 corp_code 를 찾아 data/raw/corp_codes.csv 로 저장한다.
- fnlttSinglAcntAll.json (fs_div=CFS) 원본 JSON 을 data/raw/{stock_code}_{year}_{reprt_code}.json 으로 저장한다.
- 캐시 모드: 파일이 이미 있으면 API 를 부르지 않는다. 키가 없어도 data/raw 만으로 끝까지 실행된다.
- status 코드와 수집 시각을 data/raw/collect_log.csv 에 남긴다.

실행 예 (프로젝트 최상위 폴더에서):
    python source/01_collect.py                         # 검증 모드: 롯데케미칼 2025 사업보고서 1건
    python source/01_collect.py --mode verify --stock 006650 --year 2024
    python source/01_collect.py --mode annual           # 3사 x 2021~2025 사업보고서 15건
    python source/01_collect.py --mode interim          # 3사 x 2026 반기(11012) + 1분기(11013) 6건
    python source/01_collect.py --mode all              # 21건 전체
    python source/01_collect.py --mode all --force      # 캐시 무시하고 다시 받기
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 경로·상수
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CORP_CODES_CSV = RAW_DIR / "corp_codes.csv"
COLLECT_LOG_CSV = RAW_DIR / "collect_log.csv"

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
FS_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

TARGETS = {
    "011170": "롯데케미칼",
    "006650": "대한유화",
    "011780": "금호석유화학",
}
ANNUAL_YEARS = [2021, 2022, 2023, 2024, 2025]
INTERIM_YEAR = 2026
REPRT_NAMES = {
    "11011": "사업보고서",
    "11012": "반기보고서",
    "11013": "1분기보고서",
    "11014": "3분기보고서",
}
FS_DIV = "CFS"

# DART status 코드 설명
STATUS_MSG = {
    "000": "정상",
    "010": "등록되지 않은 키",
    "011": "사용할 수 없는 키",
    "012": "접근할 수 없는 IP",
    "013": "조회된 데이터 없음",
    "014": "파일이 존재하지 않음",
    "020": "요청 제한 초과",
    "021": "조회 가능한 회사 개수 초과",
    "100": "필드의 부적절한 값",
    "101": "부적절한 접근",
    "800": "시스템 점검 중",
    "900": "정의되지 않은 오류",
    "901": "개인정보 보유기간 만료 키",
}
# 이 코드가 나오면 더 호출해도 소용없으므로 즉시 멈춘다
FATAL_STATUS = {"010", "011", "012", "020", "021", "800", "901"}

LOG_FIELDS = [
    "logged_at", "stock_code", "corp_name", "corp_code", "bsns_year", "reprt_code",
    "reprt_name", "fs_div", "source", "status", "message", "rows", "rcept_no",
    "file", "collected_at",
]

# 검증 모드에서 공시 원문과 대조할 핵심 계정 (account_id 우선, 없으면 account_nm)
VERIFY_ACCOUNTS = [
    ("매출액", ["IS", "CIS"], ["ifrs-full_Revenue"], ["매출액", "수익(매출액)", "영업수익", "매출"]),
    ("영업이익", ["IS", "CIS"], ["dart_OperatingIncomeLoss"], ["영업이익", "영업이익(손실)", "영업손실"]),
    ("자산총계", ["BS"], ["ifrs-full_Assets"], ["자산총계"]),
]
# 이자비용·차입금 매핑 후보를 미리 훑어보기 위한 키워드
MAPPING_HINT_KEYWORDS = ["이자", "금융원가", "금융비용", "차입", "사채", "유동성장기"]

API_KEY: str | None = None


# ---------------------------------------------------------------------------
# 공통 도구
# ---------------------------------------------------------------------------
def setup_console() -> None:
    """Windows 콘솔(cp949)에서 한글·기호가 깨지거나 오류 나지 않게 한다."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def load_api_key() -> str | None:
    load_dotenv(ROOT / ".env")
    key = (os.getenv("DART_API_KEY") or "").strip()
    if not key or key == "YOUR_API_KEY":
        return None
    return key


def mask(text: object) -> str:
    """문자열 안의 API 키를 가린다. 모든 출력·로그·예외 문구는 이 함수를 거친다."""
    s = str(text)
    if API_KEY:
        s = s.replace(API_KEY, "***")
    return s


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def raw_path(stock_code: str, year: int, reprt_code: str) -> Path:
    return RAW_DIR / f"{stock_code}_{year}_{reprt_code}.json"


def append_log(row: dict) -> None:
    new_file = not COLLECT_LOG_CSV.exists()
    with COLLECT_LOG_CSV.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: mask(row.get(k, "")) for k in LOG_FIELDS})


def http_get(url: str, params: dict, retries: int = 3, timeout: int = 30) -> requests.Response:
    """네트워크 오류만 재시도한다. 예외 문구의 URL 에 키가 섞이므로 mask 후 다시 던진다."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_err = e
            print(f"  [재시도 {attempt}/{retries}] {mask(type(e).__name__)}: {mask(e)}")
            time.sleep(2 * attempt)
    raise RuntimeError(mask(f"요청 실패: {url} ({last_err})"))


# ---------------------------------------------------------------------------
# 1) corp_code 찾기
# ---------------------------------------------------------------------------
def load_corp_codes(force: bool = False) -> dict[str, dict]:
    """stock_code -> {corp_code, corp_name, ...}. 캐시 CSV 가 있으면 그것을 쓴다."""
    if CORP_CODES_CSV.exists() and not force:
        with CORP_CODES_CSV.open(encoding="utf-8-sig") as f:
            rows = {r["stock_code"]: r for r in csv.DictReader(f)}
        missing = set(TARGETS) - set(rows)
        if not missing:
            print(f"[corp_code] 캐시 사용: {CORP_CODES_CSV.relative_to(ROOT)}")
            return rows
        print(f"[corp_code] 캐시에 없는 종목 {sorted(missing)} -> 다시 받습니다.")

    if not API_KEY:
        sys.exit(
            "[중단] data/raw/corp_codes.csv 가 없고 DART_API_KEY 도 없습니다.\n"
            "       .env 에 키를 넣거나, 팀에서 받은 data/raw 폴더를 넣고 다시 실행하세요."
        )

    print("[corp_code] corpCode.xml 내려받는 중...")
    resp = http_get(CORP_CODE_URL, {"crtfc_key": API_KEY}, timeout=60)
    content = resp.content
    if not zipfile.is_zipfile(io.BytesIO(content)):
        # 키 오류 등은 ZIP 대신 XML/JSON 오류 문서로 온다
        sys.exit(mask(f"[중단] corpCode.xml 이 ZIP 이 아닙니다. 응답 앞부분: {content[:300]!r}"))

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        xml_name = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
        root = ET.fromstring(zf.read(xml_name))

    collected_at = now_str()
    found: dict[str, dict] = {}
    for item in root.iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        if stock in TARGETS:
            found[stock] = {
                "stock_code": stock,
                "corp_code": (item.findtext("corp_code") or "").strip(),
                "corp_name": (item.findtext("corp_name") or "").strip(),
                "modify_date": (item.findtext("modify_date") or "").strip(),
                "collected_at": collected_at,
            }

    missing = set(TARGETS) - set(found)
    if missing:
        sys.exit(f"[중단] corpCode.xml 에서 찾지 못한 종목코드: {sorted(missing)}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with CORP_CODES_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["stock_code", "corp_code", "corp_name", "modify_date", "collected_at"])
        w.writeheader()
        for stock in TARGETS:
            w.writerow(found[stock])
    print(f"[corp_code] 저장: {CORP_CODES_CSV.relative_to(ROOT)}")
    for stock in TARGETS:
        r = found[stock]
        print(f"  {stock} {r['corp_name']} -> corp_code {r['corp_code']}")
    return found


# ---------------------------------------------------------------------------
# 2) 재무제표 원본 수집
# ---------------------------------------------------------------------------
def collect_one(corp: dict, year: int, reprt_code: str, force: bool = False) -> tuple[str, dict | None]:
    """한 건 수집. (status, json) 을 돌려준다. 캐시가 있으면 API 를 부르지 않는다."""
    stock = corp["stock_code"]
    name = TARGETS.get(stock, corp.get("corp_name", ""))
    path = raw_path(stock, year, reprt_code)
    label = f"{name}({stock}) {year} {REPRT_NAMES.get(reprt_code, reprt_code)}"
    base_log = {
        "logged_at": now_str(), "stock_code": stock, "corp_name": name,
        "corp_code": corp["corp_code"], "bsns_year": year, "reprt_code": reprt_code,
        "reprt_name": REPRT_NAMES.get(reprt_code, ""), "fs_div": FS_DIV,
        "file": path.relative_to(ROOT).as_posix(),
    }

    # 캐시
    if path.exists() and not force:
        data = json.loads(path.read_text(encoding="utf-8"))
        status = str(data.get("status", ""))
        rows = data.get("list") or []
        append_log({
            **base_log, "source": "cache", "status": status,
            "message": data.get("message", ""), "rows": len(rows),
            "rcept_no": rows[0].get("rcept_no", "") if rows else "",
            "collected_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
        print(f"[캐시] {label}: {len(rows)}행")
        return status, data

    if not API_KEY:
        append_log({**base_log, "source": "skip", "status": "", "message": "캐시 없음, API 키 없음"})
        print(f"[건너뜀] {label}: 캐시 파일이 없고 API 키도 없습니다.")
        return "NO_KEY", None

    params = {
        "crtfc_key": API_KEY, "corp_code": corp["corp_code"],
        "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": FS_DIV,
    }
    resp = http_get(FS_URL, params)
    collected_at = now_str()
    try:
        data = resp.json()
    except ValueError:
        append_log({**base_log, "source": "api", "status": "PARSE_ERROR",
                    "message": "JSON 파싱 실패", "collected_at": collected_at})
        print(f"[오류] {label}: 응답이 JSON 이 아닙니다.")
        return "PARSE_ERROR", None

    status = str(data.get("status", ""))
    message = data.get("message", "") or STATUS_MSG.get(status, "")
    rows = data.get("list") or []
    rcept_no = rows[0].get("rcept_no", "") if rows else ""

    if status == "000":
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        # 원본 그대로 저장한다 (수집 시각은 collect_log.csv 에 남긴다)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[수집] {label}: {len(rows)}행, rcept_no {rcept_no}")
    else:
        # 정상이 아니면 저장하지 않는다. 다음 실행 때 다시 시도하게 하기 위해서다.
        print(f"[status {status}] {label}: {STATUS_MSG.get(status, message)}")

    append_log({
        **base_log, "source": "api", "status": status, "message": message,
        "rows": len(rows), "rcept_no": rcept_no,
        "file": base_log["file"] if status == "000" else "",
        "collected_at": collected_at,
    })
    return status, data


# ---------------------------------------------------------------------------
# 3) 검증 모드 출력: 공시 원문과 눈으로 대조
# ---------------------------------------------------------------------------
def to_number(v: object) -> int | None:
    s = str(v or "").replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def fmt_amount(v: object) -> str:
    n = to_number(v)
    if n is None:
        return "(없음)"
    return f"{n:>22,} 원 | {n / 1e8:>14,.1f} 억원"


def find_account(rows: list[dict], sj_divs: list[str], ids: list[str], names: list[str]) -> tuple[dict | None, str]:
    cand = [r for r in rows if r.get("sj_div") in sj_divs]
    # IS 와 CIS 에 모두 있으면 IS 를 먼저 본다 (sj_divs 순서 = 우선순위)
    cand.sort(key=lambda r: sj_divs.index(r.get("sj_div")))
    for r in cand:
        if r.get("account_id") in ids:
            return r, "account_id"
    for r in cand:
        if (r.get("account_nm") or "").replace(" ", "") in [n.replace(" ", "") for n in names]:
            return r, "account_nm"
    return None, ""


def print_verify(data: dict, stock: str, year: int, reprt_code: str) -> None:
    rows = data.get("list") or []
    if not rows:
        print("  데이터가 없습니다.")
        return

    rcept_no = rows[0].get("rcept_no", "")
    sj_count: dict[str, int] = {}
    for r in rows:
        sj_count[r.get("sj_div", "?")] = sj_count.get(r.get("sj_div", "?"), 0) + 1
    rcept_set = sorted({r.get("rcept_no", "") for r in rows})

    print("\n" + "=" * 78)
    print(f" 검증: {TARGETS.get(stock, stock)}({stock}) {year} {REPRT_NAMES.get(reprt_code, reprt_code)} / fs_div={FS_DIV}")
    print("=" * 78)
    print(f" 총 {len(rows)}행 / 재무제표 구분별: {sj_count}")
    if "IS" not in sj_count and "CIS" in sj_count:
        print(" * IS 가 없고 CIS(포괄손익계산서)에만 손익이 있습니다. 02_clean.py 에서 CIS 를 사용해야 합니다.")
    print(f" rcept_no(접수번호): {', '.join(rcept_set)}")
    print(f" 공시 원문: {DART_VIEWER.format(rcept_no=rcept_no)}")
    first = rows[0]
    print(f" 당기명: {first.get('thstrm_nm', '')} / 전기명: {first.get('frmtrm_nm', '')} / 통화: {first.get('currency', '')}")

    # 보고서 종류에 따라 볼 금액 컬럼
    amount_cols = ["thstrm_amount", "frmtrm_amount"]
    if reprt_code != "11011":
        amount_cols = ["thstrm_amount", "thstrm_add_amount", "frmtrm_q_amount", "frmtrm_add_amount", "frmtrm_amount"]

    print("\n [핵심 계정] 아래 숫자를 공시 원문 연결재무제표 본문과 대조하세요.")
    for label, sj_divs, ids, names in VERIFY_ACCOUNTS:
        r, how = find_account(rows, sj_divs, ids, names)
        print(f"\n  - {label}")
        if r is None:
            print("    찾지 못함: account_id / account_nm 매핑을 확인해야 합니다.")
            continue
        print(f"    sj_div={r.get('sj_div')} / account_id={r.get('account_id')} / account_nm={r.get('account_nm')} (찾은 방법: {how})")
        for col in amount_cols:
            if col in r:
                print(f"    {col:<18}: {fmt_amount(r.get(col))}")

    # 이자비용·차입금 매핑 후보 미리 보기 (02_clean.py 매핑표 작성용)
    print("\n [매핑 후보] 이자비용·차입금 관련 계정 (account_mapping.csv 작성 참고용)")
    seen = set()
    for r in rows:
        nm = (r.get("account_nm") or "")
        if any(k in nm for k in MAPPING_HINT_KEYWORDS):
            key = (r.get("sj_div"), r.get("account_id"), nm)
            if key in seen:
                continue
            seen.add(key)
            print(f"    {r.get('sj_div'):<4} {str(r.get('account_id'))[:55]:<55} {nm:<20} {fmt_amount(r.get('thstrm_amount')).strip()}")

    print("\n 대조 방법: 위 링크를 열고 [연결재무제표] 본문에서 매출액·영업이익·자산총계를 찾아")
    print(" 당기·전기 금액이 원 단위까지 같은지 확인하세요. (원문 단위가 백만원·천원이면 환산해서 비교)")
    print("=" * 78 + "\n")


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
def build_jobs(mode: str, stock: str, year: int, reprt: str) -> list[tuple[str, int, str]]:
    if mode == "verify":
        return [(stock, year, reprt)]
    jobs: list[tuple[str, int, str]] = []
    if mode in ("annual", "all"):
        jobs += [(s, y, "11011") for s in TARGETS for y in ANNUAL_YEARS]
    if mode in ("interim", "all"):
        jobs += [(s, INTERIM_YEAR, "11012") for s in TARGETS]
        jobs += [(s, INTERIM_YEAR, "11013") for s in TARGETS]
    return jobs


def main() -> int:
    global API_KEY
    setup_console()

    p = argparse.ArgumentParser(description="DART 재무제표 원본 수집 (석유화학 3사)")
    p.add_argument("--mode", choices=["verify", "annual", "interim", "all"], default="verify",
                   help="verify=1개사 1개년 검증(기본), annual=사업보고서 15건, interim=반기·1분기 6건, all=21건")
    p.add_argument("--stock", default="011170", choices=list(TARGETS), help="검증 모드 종목코드 (기본 011170)")
    p.add_argument("--year", type=int, default=2025, help="검증 모드 사업연도 (기본 2025)")
    p.add_argument("--reprt", default="11011", choices=list(REPRT_NAMES), help="검증 모드 보고서 코드 (기본 11011)")
    p.add_argument("--force", action="store_true", help="캐시를 무시하고 API 를 다시 호출")
    p.add_argument("--sleep", type=float, default=0.7, help="API 호출 사이 대기(초)")
    args = p.parse_args()

    API_KEY = load_api_key()
    print(f"[설정] 프로젝트 폴더: {ROOT}")
    print(f"[설정] API 키: {'있음' if API_KEY else '없음 (캐시 모드로만 실행)'} / 모드: {args.mode}")

    try:
        corps = load_corp_codes(force=args.force)
        jobs = build_jobs(args.mode, args.stock, args.year, args.reprt)
        print(f"[계획] {len(jobs)}건\n")

        summary: dict[str, int] = {}
        for i, (stock, year, reprt) in enumerate(jobs, 1):
            cached = raw_path(stock, year, reprt).exists() and not args.force
            status, data = collect_one(corps[stock], year, reprt, force=args.force)
            summary[status] = summary.get(status, 0) + 1

            if args.mode == "verify" and data and status == "000":
                print_verify(data, stock, year, reprt)

            if status in FATAL_STATUS:
                print(f"[중단] status {status} ({STATUS_MSG.get(status)}). 남은 {len(jobs) - i}건은 다음에 실행하세요.")
                break
            if not cached and i < len(jobs):
                time.sleep(args.sleep)

        print("\n[요약] status 별 건수:", summary)
        print(f"[요약] 로그: {COLLECT_LOG_CSV.relative_to(ROOT)}")
        ok = summary.get("000", 0)
        return 0 if ok == len(jobs) else 1
    except Exception as e:  # 예상 못 한 오류도 키가 새지 않게 가린다
        print(f"[오류] {mask(type(e).__name__)}: {mask(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
