# 통합앱 v2 데이터 확장 안내

현재 실행·수집 기준은 프로젝트 루트 README.md와 APP_FEATURES.md입니다. `source/00_discover_companies.py` → `source/collect_expanded.py` → `source/rebuild.py`로 확장합니다. 현재 원본 317건, 기본 목록 32개 기업의 재무 데이터를 반영했습니다. 국내 전체 전수 확인은 추가로 필요합니다. 아래 내용은 제공된 기존 3사 데이터의 수집·검산 기록입니다.

# 데이터 파이프라인 메모 (김동민 -> 원승연, README 작성용)

## 실행 순서 (프로젝트 최상위 폴더에서)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # .env 에 DART_API_KEY 입력 (data/raw 가 있으면 키 없이도 실행됨)

python source/01_collect.py --mode all   # DART 원본 21건 수집 (캐시 있으면 API 호출 안 함)
python source/02_clean.py                # 계정 매핑·정제
python source/03_metrics.py              # 본 분석 지표 (metrics.csv)
python source/03b_quarterly.py           # 심화 분석 분기 지표 (quarterly_metrics.csv)
python source/04_compare.py              # 3사 비교표
```

- 01_collect.py 옵션: `--mode verify`(기본, 1개사 1개년 검증) / `annual`(사업보고서 15건) / `interim`(반기·1분기 6건) / `all`(21건), `--force`(캐시 무시)
- DART 호출: 사업보고서 3사 x 2021~2025 = 15회, 2026 반기보고서 3회, 2026 1분기보고서 3회. 연결재무제표(fs_div=CFS)

## 앱 연결 형식 (조진영 요청 반영)

- 인코딩 utf-8-sig, stock_code 6자리 문자(앞자리 0 유지), 금액 원 단위, 비율은 % 숫자(8.5% -> 8.5), 이자보상배율은 배
- metrics.csv 23컬럼 = 공통 22 + icr_basis(이자비용/금융원가). 18행
- quarterly_metrics.csv 23컬럼 = 공통 22 + icr_basis. 18행. 2025 분기·반기 행은 재무상태표 항목·ROA·ROE·성장률 빈칸
- 결측은 빈칸 (0 으로 채우지 않음), 영업적자면 이자보상배율 음수 그대로
- metrics.csv 2026H1 행과 quarterly_metrics.csv 2026H1 행의 금액·비율은 같은 값 (검산 완료)

## 결과 파일

| 파일 | 내용 |
|---|---|
| data/raw/{종목코드}_{연도}_{보고서코드}.json | DART 원본 (11011 사업, 11012 반기, 11013 1분기) |
| data/raw/corp_codes.csv | 3사 DART 고유번호 |
| data/raw/collect_log.csv | 호출별 status, 접수번호, 수집 시각 (source=api 가 실제 호출) |
| data/processed/financials_clean.csv | 정제 금액, 원 단위 긴 형식 (기간 x 계정). rcept_no 포함 |
| data/processed/account_mapping.csv | 파일별 계정 매핑 결과 (account_id / account_nm / not_found). 수기 입력 0건 |
| data/processed/metrics.csv | **팀 공통 수치 기준.** 2021~2025 FY + 2026H1 |
| data/processed/quarterly_metrics.csv | 심화 분석용. 2025Q1, 2025Q2, 2026Q1, 2026Q2, 2025H1, 2026H1 |
| data/processed/company_comparison.csv | 기간 x 지표별 3사 값, 최대·최소 기업, 차이(%p 또는 배) |
| data/processed/check_log.csv | 검산 결과 (OK / WARN / INFO) |

## 지표 기준 (보고서·앱에 그대로 인용)

- 이자보상배율: 3사 모두 본문에 이자비용 계정이 없어 **금융원가로 대체** (icr_basis=금융원가). 금융원가에는 외환손실 등이 섞여 있어 실제 이자비용 기준보다 배율이 낮게 나올 수 있음. 영업적자면 음수 그대로 저장 (앱에서 op_income < 0 이면 "적자" 표기)
- 차입금: 회사가 공시한 유동 차입금 줄 + 비유동 차입금 줄의 합. 롯데케미칼은 계정명이 "차입금및사채"(사채 포함). 리스부채는 제외
- 전기 금액: 2021 은 2021 사업보고서의 전기(2020) 금액, 2022 이후는 직전 연도 사업보고서 당기 금액 (03_metrics.py 의 PRIOR_BASIS)
- 2026H1: 매출 성장률은 2025 상반기 대비, ROA·ROE 는 순이익 x 2 / 6월 말 잔액 (annualized=Y, "연환산" 표시 필수)
- quarterly_metrics.csv: 2025 분기 말 재무상태표는 2026 보고서에 없어 빈칸. 시점 비교의 2025년 말 값은 metrics.csv 2025 행 사용
- 비교는 같은 보고서끼리: 2026Q1 vs 2025Q1 은 1분기보고서, 2026Q2·H1 vs 2025Q2·H1 은 반기보고서
- 비율은 소수 둘째 자리 반올림 저장. 앱·보고서·PPT 에서 다시 계산하지 않음 (억원 변환·표시 반올림만)

## 한계 (README·보고서에 명시)

- 2026 반기·1분기 재무제표는 감사가 아니라 검토를 받은 재무제표
- 분기 실적은 재고평가손익·환율 등 일회성·계절성 영향이 큼
- 롯데케미칼은 2024 금액(2025 보고서에서 재작성)과 2025 비교 수치(1분기 vs 반기보고서)가 보고서마다 다름. check_log.csv 참고
- 연결재무제표 본문으로는 사업부별 실적을 나눌 수 없음
