# API 명세서 v1
MODULE04 미니프로젝트04 · 2조 · 석유화학 여신 계기판

이 문서는 프로젝트가 호출하는 **외부 API**(OpenDART, OpenAI)와, 앱·스크립트가 서로 주고받는 **내부 인터페이스**(함수, 데이터 파일 형식)를 정리한 것입니다. 코드 기준 위치는 각 항목에 적었습니다.

> 실제 키는 이 문서·코드·ZIP 어디에도 없습니다. 예시의 `YOUR_API_KEY`는 자리표시입니다. **투자 권유 아님.**

---

## 0. 한눈에 보기

| 구분 | API | 용도 | 키 | 호출 위치 |
|---|---|---|---|---|
| 외부 | OpenDART `corpCode.xml` | 기업 고유번호(corp_code) 조회 | DART_API_KEY | `source/01_collect.py`, `source/00_discover_companies.py` |
| 외부 | OpenDART `fnlttSinglAcntAll.json` | 단일회사 전체 재무제표 (**분석의 핵심 원본**) | DART_API_KEY | `source/01_collect.py`, `source/collect_expanded.py` |
| 외부 | OpenDART `company.json` | 기업개황, 연결·인증 점검 | DART_API_KEY | `source/collect_expanded.py --diagnose`, `00_discover_companies.py` |
| 외부 | OpenDART `list.json` | 공시 목록 검색 (확장 기업, 공시 원문) | DART_API_KEY | `source/00_discover_companies.py`, `source/collect_audit.py` |
| 외부 | OpenDART `document.xml` | 공시 원문 파일(ZIP) 내려받기 | DART_API_KEY | `source/collect_audit.py` |
| 외부 | OpenAI `POST /v1/responses` | 챗봇 자유 질문 (선택 기능) | OPENAI_API_KEY | `app/candidates/app_minji.py` `ask_openai()` |
| 내부 | `update_company(stock)` | 앱 버튼 → DART 재수집 → 재정제 | DART_API_KEY | `app/data_update.py` |
| 내부 | `answer_question(question, key)` | 챗봇 답변 라우팅 (CSV 바로 답변 / OpenAI) | 선택 | `app/candidates/app_minji.py` |
| 내부 | 데이터 파일 | 수집 원본 JSON, 정제 CSV, 지표 CSV | 없음 | `data/raw/`, `data/processed/` |

**키가 없어도** 포함된 원본 캐시(`data/raw/`)와 CSV로 앱·재현·검증이 모두 동작합니다. 키는 재수집과 챗봇 자유 질문에만 필요합니다.

---

## 1. 공통 사항

### 1-1. 키 관리

| 항목 | 내용 |
|---|---|
| 저장 위치 | 프로젝트 루트 `.env` (제출 ZIP에 없음). 챗봇 키는 환경변수 → `.streamlit/secrets.toml` → `.env` 순서로 찾음 |
| 예시 파일 | `.env.example`: `DART_API_KEY=YOUR_API_KEY`, `OPENAI_API_KEY=YOUR_API_KEY` |
| 읽는 방법 | `python-dotenv`의 `dotenv_values()` / `load_dotenv()` |
| 자리표시 처리 | 값이 비었거나 `YOUR_API_KEY`이면 **키 없음**으로 판단하고 API를 부르지 않음 |
| 노출 방지 | 키 값과 키가 들어간 요청 URL은 화면·로그·오류 문구·CSV에 남기지 않음. 점검 결과에는 `key_loaded`, `key_format_ok`(40자 여부)만 기록 |
| 제출 전 점검 | `source/package_submission.py`가 `.env`의 키 문자열이 ZIP 대상 파일에 들어 있으면 ZIP 생성을 중단 |
| `.gitignore` | `.env`, `.streamlit/secrets.toml`, `.venv/` 등 |

### 1-2. 요청 규칙

| 항목 | OpenDART | OpenAI |
|---|---|---|
| 기본 URL | `https://opendart.fss.or.kr/api/` | `https://api.openai.com/v1/` |
| 방식 | `GET`, 쿼리스트링 | `POST`, JSON 본문 |
| 인증 | 쿼리 파라미터 `crtfc_key` | 헤더 `Authorization: Bearer {key}` |
| 타임아웃 | 15~45초 (점검 15, 재무제표 30, 원문 45) | 40초 |
| 호출 간격 | 재무제표 요청 사이 0.7초 대기 (`collect_expanded.py`) | 질문 1건당 1회 |
| 캐시 | 원본 JSON이 이미 있으면 **호출하지 않음** (`--force`로만 다시 받기) | 없음 (`store: false`) |

---

## 2. OpenDART API

공식 문서: [OpenDART 개발가이드](https://opendart.fss.or.kr/guide/main.do)

### 2-1. 기업 고유번호 `corpCode.xml`

| 항목 | 내용 |
|---|---|
| URL | `GET https://opendart.fss.or.kr/api/corpCode.xml` |
| 요청 | `crtfc_key` (필수) |
| 응답 | ZIP 파일 1개 → 안의 `CORPCODE.xml`에 전체 공시대상 기업 목록 |
| 사용 필드 | `corp_code`(8자리 고유번호), `corp_name`, `stock_code`(6자리 종목코드), `modify_date` |
| 저장 | `data/raw/corp_codes.csv` (`stock_code, corp_name, corp_code`) |

분석 대상 3사:

| 기업 | stock_code | corp_code |
|---|---|---|
| 롯데케미칼 | 011170 | 00165413 |
| 대한유화 | 006650 | 00260383 |
| 금호석유화학 | 011780 | 00106368 |

### 2-2. 단일회사 전체 재무제표 `fnlttSinglAcntAll.json` (핵심)

| 항목 | 내용 |
|---|---|
| URL | `GET https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json` |
| 호출 코드 | `source/01_collect.py` (3사 21건), `source/collect_expanded.py` `fetch()` (확장 기업) |

**요청 파라미터**

| 이름 | 필수 | 형식 | 이 프로젝트에서 쓰는 값 |
|---|---|---|---|
| `crtfc_key` | Y | 40자 | `.env`의 `DART_API_KEY` |
| `corp_code` | Y | 8자리 | 2-1 표의 고유번호 |
| `bsns_year` | Y | YYYY | 2021~2025 (연간), 2026 (분기·반기) |
| `reprt_code` | Y | 5자리 | `11011` 사업보고서, `11012` 반기보고서, `11013` 1분기보고서 (`11014` 3분기는 미사용) |
| `fs_div` | Y | CFS/OFS | **`CFS`(연결)** 먼저 요청. 확장 기업에서 `013`이면 `OFS`(별도)로 한 번 더 요청 |

**수집 범위 (분석 3사 21건)**

| 모드 | 내용 | 건수 |
|---|---|---|
| `--mode annual` | 3사 × 2021~2025 × `11011` | 15 |
| `--mode interim` | 3사 × 2026 × (`11012`, `11013`) | 6 |
| `--mode all` | 위 전체 | 21 |

확장 기업(`collect_expanded.py`)은 기업마다 `2026 11012`, `2025 11011`, `2026 11013`, `2024~2021 11011` 순으로 7건을 요청합니다.

**응답 구조**

```json
{
  "status": "000",
  "message": "정상",
  "list": [
    {
      "rcept_no": "20260814004167",
      "reprt_code": "11012",
      "bsns_year": "2026",
      "corp_code": "00165413",
      "sj_div": "BS",
      "sj_nm": "재무상태표",
      "account_id": "ifrs-full_Assets",
      "account_nm": "자산총계",
      "account_detail": "-",
      "thstrm_nm": "제 51 기 반기말",
      "thstrm_amount": "32776838723105",
      "frmtrm_nm": "제 50 기말",
      "frmtrm_amount": "31117333049679",
      "ord": "7",
      "currency": "KRW"
    }
  ]
}
```

(위 값은 `data/raw/011170_2026_11012.json`의 첫 줄, 롯데케미칼 2026 반기 자산총계)

**응답 필드 (`list` 원소)**

| 필드 | 의미 | 이 프로젝트에서의 사용 |
|---|---|---|
| `rcept_no` | 접수번호 (14자리) | 출처 추적, DART 원문 링크 `https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}` |
| `reprt_code`, `bsns_year` | 보고서 코드, 사업연도 | 기간(`period`) 결정 |
| `corp_code` | 고유번호 | 기업 매칭 |
| `sj_div` / `sj_nm` | 재무제표 구분: `BS` 재무상태표, `IS` 손익계산서, `CIS` 포괄손익계산서, `CF` 현금흐름표, `SCE` 자본변동표 | 계정 탐색 범위 |
| `account_id` | 표준 계정 ID (예: `ifrs-full_Revenue`) | 1순위 계정 매칭 |
| `account_nm` | 계정명 (회사별 표기) | 2순위 계정 매칭 (이름 규칙) |
| `account_detail` | 자본변동표 세부 구분 | 중복 계정 제거 |
| `thstrm_amount` | 당기 금액 (원, 문자열) | 지표 계산 기본값 |
| `thstrm_add_amount` | 당기 누적 금액 (분기·반기 손익) | 반기 누적 손익 |
| `frmtrm_amount`, `frmtrm_q_amount`, `frmtrm_add_amount` | 전기 금액, 전기 동분기, 전기 누적 | 재작성 전기 금액 확인, 성장률 |
| `bfefrmtrm_amount` | 전전기 금액 (사업보고서) | 평균 잔액 확인 |
| `ord`, `currency` | 정렬 순서, 통화 | 정렬, KRW 확인 |

**저장 규칙**

| 항목 | 내용 |
|---|---|
| 파일명 | `data/raw/{stock_code}_{bsns_year}_{reprt_code}.json` (예: `011170_2025_11011.json`) |
| 내용 | API 응답을 **수정 없이** 저장. 확장 수집분에만 `_collection: {fs_div, collected_at}` 메타데이터를 덧붙임 |
| 로그 | `data/raw/collect_log.csv` (`logged_at, stock_code, corp_name, corp_code, bsns_year, reprt_code, reprt_name, fs_div, source, status, message, rows, rcept_no, file, collected_at`), 확장 수집은 `expanded_collect_log.csv`, 상태 요약은 `data/processed/collection_coverage.csv` |
| 현황 | 원본 JSON 317개 (모두 `status=000`), 분석 3사 21개 포함 |

### 2-3. 기업개황 `company.json`

| 항목 | 내용 |
|---|---|
| URL | `GET https://opendart.fss.or.kr/api/company.json` |
| 요청 | `crtfc_key`, `corp_code` |
| 용도 | ① `collect_expanded.py --diagnose`: 키가 실제로 통하는지 1건 호출로 확인 ② 확장 기업 업종코드(`induty_code`) 확인 |
| 점검 결과 | `data/processed/dart_connection_status.json`에 `checked_at, key_loaded, key_format_ok, homepage_status, api_status, note`만 저장 (키 값 없음) |

### 2-4. 공시 검색 `list.json`

| 항목 | 내용 |
|---|---|
| URL | `GET https://opendart.fss.or.kr/api/list.json` |
| 주요 요청 | `crtfc_key`, `corp_code`(선택), `bgn_de`, `end_de`(YYYYMMDD), `pblntf_detail_ty`(예: `A001` 사업보고서, `A002` 반기보고서, `F001`/`F002` 감사보고서), `last_reprt_at=Y`(최종보고서만), `page_no`, `page_count=100` |
| 응답 | `status, message, page_no, page_count, total_count, total_page, list[]` (`corp_code, corp_name, stock_code, corp_cls, report_nm, rcept_no, rcept_dt` 등) |
| 용도 | 확장 기업 목록 만들기(`00_discover_companies.py`, 2022-01-01~2026-09-30 사업보고서 제출기업), 공시 원문 접수번호 찾기(`collect_audit.py`) |
| 캐시 | `.deck_work/discovery/`, `data/raw/audit/{corp_code}_{종류}_list.json` |

### 2-5. 공시서류 원본 `document.xml`

| 항목 | 내용 |
|---|---|
| URL | `GET https://opendart.fss.or.kr/api/document.xml` |
| 요청 | `crtfc_key`, `rcept_no` |
| 응답 | 공시 원문 ZIP (XML 본문) |
| 용도 | 재무제표 API가 `013`(미제공)인 기업의 감사보고서 본표에서 핵심 수치 추출 (`build_audit_metrics.py`), 주석 차입금 검증 (`apply_verified_notes.py`) |
| 저장 | `data/raw/audit/` (ZIP 원본 보존). 절차는 `AUDIT_DATA_GUIDE.md` |

### 2-6. OpenDART 상태 코드와 처리

| status | 의미 | 프로젝트 처리 |
|---|---|---|
| `000` | 정상 | 저장. 단, `list`가 비면 `EMPTY_RESPONSE`로 기록하고 재확인 |
| `013` | 조회된 데이터 없음 | 공시 미제공. CFS였으면 OFS로 한 번 더 요청, 그래도 없으면 `013` 기록 (**결측을 0으로 채우지 않음**) |
| `010` / `011` | 등록되지 않은 키 / 사용할 수 없는 키 | **즉시 중단** (더 불러도 소용없음) |
| `012` | 접근할 수 없는 IP | 즉시 중단 |
| `014` | 파일이 존재하지 않음 | 기록 후 다음 건 |
| `020` | 요청 제한 초과 | 즉시 중단, 다음 날 재시도 |
| `021` | 조회 가능한 회사 수 초과 | 즉시 중단 |
| `100` / `101` | 필드 값 부적절 / 부적절한 접근 | 기록 후 다음 건 |
| `800` | 시스템 점검 | 즉시 중단 |
| `900` | 정의되지 않은 오류 | 기록 후 다음 건 |
| `901` | 개인정보 보유기간 만료 키 | 즉시 중단 |

즉시 중단 코드 묶음은 코드의 `FATAL_STATUS` / `FATAL` = `{010, 011, 012, 020, 021, 800, 901}`입니다. `000`이 아닌 응답은 원본 파일로 저장하지 않으므로(로그에만 기록) 다음 실행 때 자동으로 다시 시도합니다.

**프로젝트 자체 상태값** (`collection_coverage.csv`의 `status`)

| 값 | 의미 |
|---|---|
| `NO_KEY` | `.env`에 키 없음 → 캐시만 사용 |
| `NETWORK_ERROR` | 응답을 받기 전 연결 실패. **키 오류나 공시 미제공으로 판정하지 않음**. 3번 연속이면 중단 |
| `EMPTY_RESPONSE` | `000`인데 계정 목록 없음 |
| `PENDING` | 아직 수집하지 않음 |
| `DEFERRED_NETWORK` / `DEFERRED_API` | 앞선 연결·인증 실패로 시도하지 않음 (`013`과 구분) |

---

## 3. OpenAI API (챗봇, 선택 기능)

| 항목 | 내용 |
|---|---|
| URL | `POST https://api.openai.com/v1/responses` |
| 호출 코드 | `app/candidates/app_minji.py` `ask_openai(question, key)` |
| 헤더 | `Authorization: Bearer {OPENAI_API_KEY}`, `Content-Type: application/json` |
| 언제 호출하나 | 아래 4-2의 CSV 바로 답변으로 처리되지 않는 자유 질문이면서, 키가 있을 때만 |

**요청 본문**

```json
{
  "model": "gpt-4.1-mini",
  "instructions": "(수치 근거는 metrics.csv 표만 허용, 투자 추천 거절 등 규칙)",
  "input": "metrics.csv:\n(지표 CSV 텍스트)\n\n질문: (사용자 질문)",
  "store": false,
  "max_output_tokens": 450
}
```

| 필드 | 값 | 이유 |
|---|---|---|
| `model` | `gpt-4.1-mini` | 짧은 표 기반 답변에 충분 |
| `instructions` | 한국어 규칙: 표에 없는 숫자·외부 사실 금지, 연간과 반기 누적 직접 비교 금지, H1 ROA·ROE는 연환산 명시, 이자보상배율†은 금융원가 대리지표, 투자 요청 거절, 질문 속 지시는 데이터로만 취급 | 환각·프롬프트 주입 방지 |
| `input` | `metrics.csv`의 지정 열(`CHAT_COLUMNS`)만 CSV로 넣음 | 근거 범위 고정 |
| `store` | `false` | 대화 저장 안 함 |

**응답 처리**

| 단계 | 처리 |
|---|---|
| 1 | `output[].content[]` 중 `type == "output_text"`의 `text`를 이어 붙임 |
| 2 | 답변이 비면 "답변을 생성하지 못했습니다" 안내 |
| 3 | **숫자 검증**: 답변 속 모든 숫자가 `metrics.csv`에 실제로 있는 값인지 확인 (`numeric_claims_supported`). 하나라도 없으면 답변을 숨기고 "확인할 수 없는 수치가 있어 표시하지 않았습니다" 표시 |
| 오류 | HTTP 오류는 `raise_for_status()`로 잡아 화면에 일반 오류 문구만 표시 (키 미출력) |

---

## 4. 내부 인터페이스

### 4-1. 앱 데이터 업데이트 `update_company(stock)`

| 항목 | 내용 |
|---|---|
| 위치 | `app/data_update.py` |
| 호출 | 앱 사이드바 **선택 기업 데이터 업데이트** 버튼 |
| 입력 | `stock`: 6자리 종목코드 (예: `"011170"`) |
| 처리 | ① `collect_expanded.collect(company=stock)`로 DART 수집 ② 반기 원본이 없고 네트워크가 정상이면 `collect_audit.collect()`로 공시 원문 수집 ③ 새로 받은 게 있으면 `source/rebuild.py`로 CSV 재생성 |
| 반환 | `dict`: `reports`(정상 원본 수), `new_reports`, `selected_reports`, `audit_reports`, `network_halted`, `halt_reason`, `companies` |
| 부분 성공 | 일부 요청이 실패해도 성공한 원본은 즉시 화면 CSV에 반영 |

연결 점검 버튼(**DART 연결·인증 점검**)은 `collect_expanded.diagnose()`를 부르고 2-3의 결과 dict를 반환합니다.

### 4-2. 챗봇 `answer_question(question, key)`

| 순서 | 조건 | 결과 | 키 필요 |
|---|---|---|---|
| 1 | 질문에 투자·매수·매도·주가 전망 등 (`INVESTMENT_PATTERN`) | 거절 + **투자 권유 아님** 안내 | 없음 |
| 2 | 기업 1개 · 기간 1개 · 지표 1개가 명시됨 (`direct_metric_answer`) | `metrics.csv` 해당 칸 값으로 바로 답변. 예: `롯데케미칼 2026H1 이자보상배율` → "0.44배" | 없음 |
| 3 | 기간 1개 · 지표 1개 + "가장 높/낮" (`rank_metric_answer`) | 분석 대상 3사 순위로 답변. 예: `2025 부채비율 가장 낮은 기업` | 없음 |
| 4 | 그 밖의 자유 질문, 키 없음 | 키가 필요하다는 안내와 질문 예시 | - |
| 5 | 그 밖의 자유 질문, 키 있음 | 3장의 OpenAI 호출 | OPENAI_API_KEY |

지원 지표 이름: 매출 성장률, 영업이익률, 부채비율, ROA, ROE, 이자보상배율, 차입금 의존도.

### 4-3. 명령행 인터페이스 (스크립트)

| 명령 | 키 | 설명 |
|---|---|---|
| `python source/01_collect.py --mode {verify,annual,interim,all} [--stock 011170] [--year 2025] [--force]` | 필요 (캐시 있으면 불필요) | 분석 3사 재무제표 수집 |
| `python source/collect_expanded.py --diagnose` | 필요 | 키 인식·API status 점검 (키 값 미출력) |
| `python source/collect_expanded.py --company 010950` / `--all` | 필요 | 확장 기업 수집 |
| `python source/00_discover_companies.py` | 필요 | 확장 기업 목록 생성 |
| `python source/rebuild.py` | 불필요 | 정제 → 지표 → 품질표 → 공시 원문 지표 → 비교 데이터 → Q2 대조 전체 재생성 |
| `python source/validate_data.py` | 불필요 | 데이터 정합성 검증 |
| `python source/test_credit_logic.py` 등 `test_*.py` | 불필요 | 단위 테스트 |
| `python source/render_charts.py`, `render_report.py` | 불필요 | 차트 PNG, 요약보고서 PDF |

---

## 5. 데이터 파일 명세 (앱이 읽는 형식)

모든 CSV는 `utf-8-sig`(엑셀에서 한글이 깨지지 않음)입니다. 금액은 **원 단위**, 비율은 %, 배율은 배입니다.

### 5-1. `data/processed/metrics.csv` (연간·반기 지표, 313행)

| 열 | 형식 | 설명 | 예 (롯데케미칼 2026H1) |
|---|---|---|---|
| `corp_name`, `stock_code` | 문자 | 기업명, 종목코드 | 롯데케미칼, 011170 |
| `period` / `period_type` | 문자 | `2021`~`2025`, `2026H1` / `FY`, `H1` | 2026H1 / H1 |
| `revenue`, `op_income` | 원 | 매출액, 영업이익 | 10676890909344, 183616733490 |
| `net_income`, `net_income_owner` | 원 | 당기순이익, 지배기업 소유주 순이익 | |
| `assets`, `liabilities`, `equity`, `equity_owner` | 원 | 자산, 부채, 자본, 지배 자본 | |
| `interest_expense` | 원 | 이자비용 (없으면 금융원가) | 412702911885 |
| `borrowings` | 원 | 차입금 (단기·장기 차입금, 사채, 유동성 대체분, 리스부채 제외) | 10265441969871 |
| `sales_growth` | % | 매출 성장률 | 18.8 |
| `op_margin` | % | 영업이익률 | 1.72 |
| `roa`, `roe` | % | ROA, ROE (H1은 연환산) | 1.39, 4.03 |
| `debt_ratio` | % | 부채비율 | 76.76 |
| `icr` | 배 | 이자보상배율† | 0.44 |
| `borrow_dep` | % | 차입금 의존도 | 31.32 |
| `annualized` | Y/N | 연환산 여부 | Y |
| `icr_basis` | 문자 | `이자비용` 또는 `금융원가` | 금융원가 |
| `fs_div` | CFS/OFS | 연결/별도 | CFS |
| `roe_basis` | 문자 | ROE 산식 기준 | 지배 순이익/지배 자본 |
| `data_source` | 문자 | `DART_FINANCIAL_API` 또는 `AUDIT_XML`(공시 원문) | DART_FINANCIAL_API |
| `fiscal_end`, `rcept_no`, `source_url` | 문자 | 결산월, 접수번호, 원문 링크 (공시 원문 경로일 때) | |

### 5-2. 그 밖의 파일

| 파일 | 행 수 | 주요 열 |
|---|---|---|
| `quarterly_metrics.csv` | 288 | `period`(2025Q1~2026Q2), `period_end`, 금액 열, `sales_growth_yoy`, `op_margin`, `roa_ann`, `roe_ann`, `debt_ratio`, `icr`, `borrow_dep`, `icr_basis` |
| `financials_clean.csv` | 7,831 | `account_key`(표준화한 계정), `account_id`, `account_nm`, `value_krw`, `rcept_no`, `sj_div`, `reprt_code`, `amount_col`(사용한 금액 열), `source_file`, `fs_div` |
| `account_mapping.csv` | 5,706 | `account_key`, `description`, `match_method`(ID 매칭/이름 규칙), `account_id`, `account_nm`, `source_file` |
| `company_comparison.csv` | 77 | `period, metric, metric_name, unit`, 기업별 값 열, `max_corp, min_corp, gap, gap_unit, annualized` |
| `collection_coverage.csv` | 448 | `corp_name, stock_code, corp_code, period, year, report_code, status, fs_div, rows, rcept_no, note` |
| `events.csv` | 4 | `corp_name, date, event, type, source_url` |
| `review_checklist.csv` | - | `corp_name, period, category, item, finding, status, flag, rcept_no, note_ref, source_url, reviewer, reviewed_at` (주석·산업 수기 정리, 모든 줄에 출처) |

---

## 6. 오류 처리 원칙 요약

1. **결측은 0이 아니다**: 미제공(`013`)·연결 실패·계정 누락은 빈칸으로 두고 상태를 기록합니다. 차입금 매핑이 불완전하면 관리 단계 판정을 보류합니다.
2. **연결 실패와 미제공을 구분**: `NETWORK_ERROR`는 `013`으로 기록하지 않습니다.
3. **소용없는 재호출 금지**: 키·IP·한도 오류는 즉시 멈춥니다.
4. **키는 어디에도 출력하지 않음**: 오류 문구에도 "인증키와 URL은 출력하지 않음"으로만 표시합니다.
5. **원본 보존**: API 응답 JSON과 공시 원문 ZIP은 수정 없이 보관하고, 가공은 `data/processed/`에서만 합니다.

---

## 7. 참고 링크

- [OpenDART 단일회사 전체 재무제표](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020)
- [OpenDART 공시검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001) · [기업개황](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002) · [고유번호](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018) · [공시서류원본파일](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)

관리 단계와 기준선은 분석용 참고값이며 실제 은행 심사 기준이 아닙니다. **투자 권유 아님.**
