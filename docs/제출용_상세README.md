> **GitHub 포트폴리오 안내:** 이 문서는 팀 제출 당시의 README입니다. 저장소에서는 `docs/` 폴더로 옮겨 경로 링크가 맞지 않을 수 있고, `video/` 폴더는 용량 때문에 제외, `data/raw/`는 `data/raw_DART원본.zip`으로 압축했습니다.

# 석유화학 여신 계기판: 재무제표 기반 기업 경영성과 분석
MODULE04 미니프로젝트04 · 2조

DART OpenAPI로 석유화학 3사의 재무제표를 수집하고, 성장성·수익성·안정성 지표를 계산해 **은행 심사역의 시각**으로 비교한 프로젝트입니다. 결과는 Streamlit 앱(여신 계기판), 분석결과 요약보고서, 발표 PPT로 정리했습니다.

> 관리 단계와 기준선(이자보상배율 1배, 차입금 의존도 30%)은 분석용 참고선이며 실제 은행 심사 기준이 아닙니다. **투자 권유 아님.**

---

## 1. 한눈에 보기

| 항목 | 내용 |
|---|---|
| 주제 | 불황 4년, 은행은 누구의 빚을 걱정하나: 석유화학 3사 재무제표로 본 여신 관리 신호 |
| 분석 대상 | **롯데케미칼(011170) · 대한유화(006650) · 금호석유화학(011780)** |
| 분석 기간 | 연간 2021~2025 (사업보고서) + 2026 상반기 누적 (반기보고서), 분기 2025Q1~2026Q2 |
| 데이터 | DART OpenAPI `fnlttSinglAcntAll` 전체 재무제표, **연결(CFS)** 기준, 3사 원본 JSON 21개 |
| 핵심 지표 | 매출 성장률 · 영업이익률 · 부채비율 · ROA · ROE (+ 이자보상배율†, 차입금 의존도) |
| 결과물 | Streamlit 앱, 비교 차트 7개, 요약보고서 PDF, 발표 PPT, **AI 음성 발표 영상(시연 포함)·시연 영상**, API 명세서 |

### 기업 선정 이유

1. **같은 업종, 다른 구조**: 셋 다 석유화학이지만 범용 NCC 중심(롯데케미칼·대한유화)과 합성고무·페놀 등 스페셜티 비중이 큰 금호석유화학으로 제품 구성이 다릅니다. 같은 불황에서 지표가 어떻게 갈리는지 비교할 수 있습니다.
2. **규모 차이**: 2025년 매출 기준 롯데케미칼 약 18.5조, 금호석유화학 약 7조, 대한유화 약 3.3조로 규모가 달라 "규모가 위험을 막아주나"를 물을 수 있습니다.
3. **은행이 실제로 움직인 업종**: 2024년 롯데케미칼 회사채 재무특약 미충족·은행 보증, 2026년 대산 석유화학 사업재편 등 여신 관리 이슈가 실제로 있었습니다(`data/processed/events.csv`).
4. **공시 조건**: 3사 모두 상장사로 2021~2026.06 사업·반기·분기보고서가 DART에 있어 같은 기준으로 수집할 수 있습니다.

### 핵심 결론 (출처: `data/processed/metrics.csv`)

| 결론 | 근거 |
|---|---|
| 불황에서 갈린 건 규모가 아니라 **적자 여부** | 영업적자 연도: 롯데케미칼 4년(2022~2025), 대한유화 3년(2022~2024), 금호석유화학 0년 |
| **부채비율보다 이자보상배율**이 먼저 경고 | 2024년 말 부채비율이 가장 낮은 대한유화(22.80%)도 이자보상배율† 3년 연속 1배 미만(2022~2024) |
| 2026 상반기 흑자 전환만으로 여신 조건을 풀지 않음 | 2026H1 영업이익률 롯데 1.72% · 대한 3.86% · 금호 9.84%로 3사 흑자지만, 롯데 이자보상배율† 0.44배·차입금 의존도 31.3%로 **집중 관리** 칸 유지 |

---

## 2. 폴더 구조

```text
MODULE04_미니프로젝트04_2조/
├─ README.md                  ← 이 파일 (실행·재현 방법)
├─ requirements.txt           ← 필요한 파이썬 패키지
├─ .env.example               ← 환경변수 이름만 (실제 키 없음)
├─ run_app.bat                ← Windows 더블클릭 실행
├─ APP_FEATURES.md            ← 앱 기능·계산·검증 상세
├─ API_명세서_v1.md           ← OpenDART·OpenAI 호출 규격, 내부 함수, 데이터 파일 형식
├─ AUDIT_DATA_GUIDE.md        ← 공시 원문(감사보고서) 추출·재현 절차
├─ TROUBLESHOOTING.md         ← 작업 중 막힌 문제와 해결 기록
├─ .gitignore                 ← .env 등 비공개 파일 제외 목록
├─ .streamlit/config.toml     ← 앱 테마
├─ source/                    ← 수집·정제·지표·차트·보고서·테스트 파이썬 소스
├─ data/
│  ├─ raw/                    ← DART 수집 원본 (JSON 317개, 수집 로그, 기업 고유번호, audit/)
│  └─ processed/              ← 정제 재무 데이터·지표·기업 비교 데이터 (CSV)
├─ app/
│  ├─ app.py                  ← Streamlit 실행 진입점
│  ├─ candidates/app_minji.py ← 실제 화면 구현 (app.py가 실행)
│  └─ *.py                    ← 화면 모듈 (계기판·인사이트·주석 확인·테마 등)
├─ colab/                     ← Google Colab 실행 노트북
├─ output/
│  ├─ charts/                 ← 경영성과 비교 차트 PNG 7개
│  ├─ app_screens/            ← 탭별 실행 화면 5장
│  └─ streamlit_screen.png    ← Streamlit 실행 화면 (근거 지표 탭)
├─ report/
│  └─ 분석결과_요약보고서.pdf
├─ presentation/
│  └─ 미니프로젝트04_발표자료.pptx
└─ video/
   ├─ 미니프로젝트04_발표영상_v1.mp4   ← AI 음성 발표 영상 18분 51초 (시연 포함)
   ├─ 미니프로젝트04_발표영상_v1.srt   ← 발표 영상 자막
   ├─ 미니프로젝트04_시연영상_v1.mp4   ← 앱 시연만 2분 50초
   ├─ 미니프로젝트04_시연영상_v1.srt   ← 시연 영상 자막
   └─ 영상_내레이션_원고_v1.md         ← 내레이션 원고·슬라이드별 시작 시각
```

---

## 3. 실행 방법 (API 키 없이 바로 실행)

포함된 CSV로 앱이 동작하므로 **DART 키 없이 실행됩니다.** Python **3.9 이상**이면 됩니다.
맥 기본 `python3`(3.9, Streamlit 1.50까지 설치됨)와 최신 환경(Python 3.13, Streamlit 1.65) 두 곳에서 5개 탭·챗봇·공시 원문 경로까지 눌러 보며 오류 0건을 확인했습니다.

> zip은 더블클릭으로 안을 들여다보지 말고 **반드시 압축을 푼 뒤** 실행하세요. (Windows: 오른쪽 클릭 → 모두 압축 풀기)
> 명령은 **한 줄씩** 복사해 붙여넣고 Enter를 누릅니다.

### Windows

**방법 1. 더블클릭 (가장 쉬움)**: 압축을 푼 폴더 안에서 `run_app.bat`가 보일 때까지 들어가 더블클릭 → 패키지 설치(처음 1~3분) 후 브라우저가 `http://localhost:8501`로 열립니다. 까만 창은 앱을 쓰는 동안 닫지 마세요.

**방법 2. 명령 프롬프트(CMD)**

**윈도우 "압축 풀기"는 폴더 안에 같은 이름의 폴더를 한 번 더 만듭니다** (`...\MODULE04_미니프로젝트04_2조\MODULE04_미니프로젝트04_2조`). 두 번째 줄이 안쪽 폴더로 자동으로 들어갑니다. 안쪽 폴더가 없으면 아무 일도 일어나지 않으니 그대로 입력하면 됩니다.

```bat
cd /d "%USERPROFILE%\Downloads\MODULE04_미니프로젝트04_2조"
```
```bat
if exist MODULE04_미니프로젝트04_2조\README.md cd MODULE04_미니프로젝트04_2조
```
```bat
dir README.md
```
```bat
py -m venv .venv
```
```bat
.venv\Scripts\activate
```
```bat
py -m pip install -r requirements.txt
```
```bat
py -m streamlit run app/app.py
```

- 첫 줄의 경로는 압축을 푼 위치에 맞게 바꿉니다. 탐색기 주소창의 경로를 복사해 `cd /d "..."` 안에 붙여도 됩니다.
- `dir README.md`에서 "파일을 찾을 수 없습니다"가 나오면 아직 바깥 폴더입니다. `cd MODULE04_미니프로젝트04_2조`를 한 번 더 입력합니다.

### macOS (터미널)

터미널에 `cd `(cd와 공백 한 칸)를 입력한 뒤, Finder에서 **압축을 푼 폴더를 터미널 창으로 끌어다 놓고** Enter를 누릅니다. 폴더가 다운로드가 아니라 바탕화면 등 다른 곳에 있어도 경로가 자동으로 들어가므로, 경로를 직접 타이핑하는 것보다 확실합니다.

```bash
ls README.md requirements.txt
```
```bash
python3 -m venv .venv
```
```bash
source .venv/bin/activate
```
```bash
python -m pip install -r requirements.txt
```
```bash
python -m streamlit run app/app.py
```

- `ls`에서 `No such file`이 나오면 바깥 폴더에 있는 것입니다. `cd MODULE04_미니프로젝트04_2조`를 한 번 더 입력합니다.
- 브라우저에서 `http://localhost:8501`이 열립니다(이미 다른 앱이 켜져 있으면 8502). 종료는 터미널에서 `Control + C`.
- 다른 프로젝트를 돌리던 터미널이면 먼저 `deactivate`로 이전 가상환경을 끄고, 이 폴더에서 새로 `.venv`를 만듭니다. 가상환경은 폴더마다 따로라서 패키지도 이 폴더에서 다시 설치해야 합니다.

### Google Colab

1. 압축을 푼 `MODULE04_미니프로젝트04_2조` 폴더를 **내 드라이브 맨 위**에 이름 그대로 올립니다.
2. `colab/MODULE04_미니프로젝트04_2조_colab.ipynb`를 Colab에서 열고 `런타임 → 모두 실행`.
3. 출력되는 `▶ 앱 주소`(https://….trycloudflare.com)를 클릭합니다. 드라이브에 폴더가 없으면 노트북이 zip 업로드 버튼을 띄웁니다.

### 실행이 안 될 때

| 증상 | 해결 |
|---|---|
| `ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'` | 바깥 폴더에 있다는 뜻입니다(윈도우 압축 풀기로 같은 이름 폴더가 두 번 생김). `cd MODULE04_미니프로젝트04_2조`로 안쪽 폴더에 들어간 뒤 다시 입력합니다. 가상환경은 켜진 그대로 둬도 됩니다 |
| `cd: no such file or directory` (맥) | 압축을 푼 위치가 입력한 경로와 다릅니다(예: 다운로드가 아니라 바탕화면). `cd ` 뒤에 Finder의 폴더를 끌어다 놓습니다 |
| `No module named streamlit` / `No module named 'plotly'` | `pip install -r requirements.txt`가 끝까지 성공하지 않은 상태입니다. 가상환경이 켜진(`(.venv)` 표시) 상태에서 `python -m pip install -r requirements.txt`를 다시 실행하고 마지막 줄이 `Successfully installed`인지 확인합니다 |
| `'pip'` 또는 `'streamlit'` 명령을 찾을 수 없음 | 앞에 `py -m`(Windows) / `python -m`(Mac, 가상환경 켠 뒤) 붙이기, 또는 `run_app.bat` |
| `SyntaxError: f-string` · `StreamlitInvalidWidthError` · `popover() got an unexpected keyword argument 'type'` | 2026-10-10 이전 ZIP의 오류입니다(파이썬 3.9·Streamlit 1.50 미지원 문법). 이 ZIP에서는 고쳤으니 최신 ZIP으로 다시 받습니다 |
| 경로에 `.zip\`이 들어감, 파일이 비어 보임 | 압축을 풀지 않은 상태. 압축 해제 후 실행 |
| 화면에 데이터가 없음 | 반드시 **README.md가 있는 폴더**에서 `streamlit run app/app.py` 실행 |
| 리눅스·Colab에서 차트 한글이 네모로 깨짐 | `apt-get install -y fonts-nanum` 후 다시 실행 |
| Colab 주소가 하얀 화면 | 10~20초 뒤 새로고침, 안 되면 출력된 `대체 주소` |

그 밖의 사례는 `TROUBLESHOOTING.md`에 있습니다.

---

## 4. Streamlit 필수 기능 대응표

| 필수 기능 | 앱 위치 | 내용 |
|---|---|---|
| 기업 선택 | 사이드바 `심사 대상 기업` · `비교 기업` | 대상 1곳 + 비교 기업 여러 곳 선택 |
| 분석 연도 선택 | 사이드바 `분석 연도` | 2021~2025, 2026H1 |
| 주요 KPI 카드 | `근거 지표` 탭 01 | 매출 성장률·영업이익률·부채비율·ROA·ROE·이자보상배율†, 전기 대비 증감, 산식 툴팁 |
| 재무지표 비교표 | `근거 지표` 탭 02 | 기업별 매출액·성장률·영업이익률·부채비율·ROE, 전체 지표 표 펼침 |
| 기업 비교 차트 | `근거 지표` 탭 03·04, `은행 판단` 탭 | 매출·영업이익 막대, 부채비율·차입금 의존도 막대, 여신 계기판 게이지·관리 지도 |
| 연도별 추이 그래프 | `근거 지표` 탭 05 | 이자보상배율†·영업이익률 2021~2026H1 (상반기는 점선·빈 마름모) |
| 분석 결과 표시 | `은행 판단` · `RM 인사이트` 탭 | 3초 요약 경고등, 관리 단계 이동, 2022년 충격 시나리오, 심사 메모, RM 상담 방향 |

### 탭 구성

| 탭 | 내용 |
|---|---|
| 은행 판단 | 여신 계기판(이자보상배율·차입금 의존도 게이지), 3초 요약 경고등, 관리 단계 이동, 버틸 여력(2022년 충격), 관리 지도·헤드룸, **주석·산업 확인**(차입금 구성·손상·담보·약정·신용평가·업황, 출처·DART 원문 링크), 심사 메모 |
| 근거 지표 | KPI 카드, 비교표, 매출·영업이익·안정성 막대, 연도별 추이 |
| 충격 분기 | 2분기 영업이익률 전년 대비 변화, 2025 vs 2026 분기 실적, 2025년 말 → 3월 말 → 6월 말 부채비율·차입금 의존도, 산업 확인(원료 조달·스프레드) |
| RM 인사이트 | 선택 기업 숫자로 만든 인사이트, RM 상담 방향 4개, 이자보상배율 변화 원인 분해(영업이익 요인 vs 금융원가 요인) |
| 데이터 기준 | 산식, 기업 범위·수집 상태, 품질표, CSV 내려받기 |

오른쪽 아래 **재무 데이터 챗봇**은 키 없이도 `metrics.csv` 값으로 바로 답합니다(예: `롯데케미칼 2026H1 이자보상배율`, `2025 부채비율 가장 낮은 기업`). 자유 질문(AI 답변)은 `OPENAI_API_KEY`가 있을 때만 열리며, 투자 추천은 거절합니다. 탭별 화면은 `output/app_screens/`에 있습니다.

---

## 5. 분석 과정과 재현

### 5-1. 파이프라인

| 단계 | 스크립트 | 입력 → 출력 |
|---|---|---|
| ① 기업 고유번호 조회 | `source/00_discover_companies.py` | DART corpCode → `data/raw/corp_codes.csv`, `data/processed/company_registry.csv` |
| ② 재무제표 수집 | `source/01_collect.py`, `collect_expanded.py` | 사업보고서(11011)·반기(11012)·1분기(11013) → `data/raw/{종목코드}_{연도}_{보고서코드}.json`, `collect_log.csv` |
| ③ 정제·계정 추출 | `source/02_clean.py` | 원본 JSON → `financials_clean.csv`, `account_mapping.csv` (원화 금액·계정 매핑·출처) |
| ④ 지표 계산 | `source/03_metrics.py`, `03b_quarterly.py` | → `metrics.csv`(연간·반기), `quarterly_metrics.csv`(분기), `q2_reconciliation.csv` |
| ⑤ 기업 비교 | `source/04_compare.py` | → `company_comparison.csv` |
| ⑥ 차트·보고서 | `source/render_charts.py`, `render_report.py` | → `output/charts/*.png`, `report/분석결과_요약보고서.pdf` |
| 전체 재현 | `source/rebuild.py` | ③~⑤와 품질표를 한 번에 재실행 |
| 검증 | `source/validate_data.py`, `test_*.py` | 데이터 정합성·관리 단계 로직·수집 로직 테스트 |

### 5-2. 키 없이 재현 (원본 캐시 사용)

`data/raw/`의 원본으로 정제·지표·차트·보고서를 다시 만들고 검증합니다. 프로젝트 최상위에서 실행합니다(Windows는 `python` 대신 `py`).

```bash
python source/rebuild.py              # 정제 → 지표 → 비교 데이터 재생성
python source/validate_data.py        # 데이터 검증
python source/test_credit_logic.py    # 관리 단계·시나리오 로직 테스트 (8개)
python source/test_audit_metrics.py   # 공시 원문 지표 테스트 (6개)
python source/test_dart_collection.py # 수집·부분 성공·계정 중복 테스트 (8개)
python source/render_charts.py        # output/charts/ 차트 7개
python source/render_report.py        # report/분석결과_요약보고서.pdf
```

제출 전 위 명령을 새 폴더에서 다시 실행해 `rebuild.py` 결과가 포함된 `data/processed/`와 **한 글자도 다르지 않음**, 테스트 전부 통과, 앱 5개 탭 실행 오류 0건을 확인했습니다.

### 5-3. DART에서 다시 수집 (키 필요)

1. [OpenDART](https://opendart.fss.or.kr)에서 인증키를 발급받습니다.
2. `.env.example`을 복사해 `.env`를 만들고 값을 넣습니다. **`.env`는 절대 제출·공유하지 않습니다.**

   ```text
   DART_API_KEY=발급받은키
   OPENAI_API_KEY=발급받은키   # 선택: 챗봇 자유 질문용
   ```

3. 연결 점검 후 수집·재현합니다.

   ```bash
   python source/collect_expanded.py --diagnose      # 키 인식·API status만 확인 (키 값은 출력 안 함)
   python source/01_collect.py --mode all            # 분석 대상 3사 21건 (캐시가 있으면 API 호출 생략, --force로 다시 받기)
   python source/rebuild.py
   python source/validate_data.py
   ```

   확장 기업까지: `python source/00_discover_companies.py` → `python source/collect_expanded.py --all` → `rebuild.py`. 특정 기업만: `python source/collect_expanded.py --company 010950`. 앱 사이드바의 **DART 연결·인증 점검**, **선택 기업 데이터 업데이트** 버튼도 같은 기능입니다.

---

## 6. 재무지표 정의

| 지표 | 산식 | 의미 |
|---|---|---|
| 매출 성장률 | (당기 매출 ÷ 전기 동일 기간 매출 - 1) × 100 | 성장성 |
| 영업이익률 | 영업이익 ÷ 매출 × 100 | 수익성 (본업) |
| ROA | 당기순이익 ÷ 평균 자산 × 100 | 수익성 (자산 효율) |
| ROE | 지배기업 소유주 순이익 ÷ 평균 지배기업 소유주 자본 × 100 | 수익성 (주주 자본) |
| 부채비율 | 부채 ÷ 자본 × 100 | 안정성 |
| 이자보상배율† | 영업이익 ÷ 이자비용 (**3사 모두 금융원가로 대체**) | 이자 감당 능력 · 1배 미만 = 영업이익으로 이자 못 냄 |
| 차입금 의존도 | 차입금 ÷ 자산 × 100 (단기·장기 차입금, 사채, 유동성 대체분 포함 / 리스부채 제외) | 안정성 · 30% 참고선 |

단위: 금액 억원, 비율 %·%p, 배율 배.

### 분석 규칙과 주의사항

- **연결(CFS) 기준**입니다. CFS가 API에서 미제공(013)인 확장 기업만 별도(OFS)를 쓰며 `fs_div`로 추적합니다.
- **이자보상배율†**: 3사 모두 손익계산서에 `이자비용` 계정이 없어 `금융원가`로 대체했습니다(`icr_basis` 열). 금융원가에는 외환손실 등이 포함될 수 있어 실제 이자보상배율보다 **낮게** 나올 수 있습니다.
- **H1(상반기)**: ROA·ROE는 순이익 × 2 ÷ 기말 잔액으로 연환산합니다. 반기 누적 금액은 연간 금액과 직접 비교하지 않습니다.
- **대한유화 2025**: 2025-04-30 ㈜한주 연결 편입으로 연결 범위가 바뀌었습니다. 2025년 성장률·평균 잔액 해석 시 주의.
- **롯데케미칼 2025 매출 성장률(-7.10%)**: 2025 사업보고서의 재작성된 전기 금액 기준입니다.
- **2025Q2 분기 실적**: 반기보고서의 3개월 표시액을 사용하고 H1-Q1과 다르면 `q2_reconciliation.csv`에 기록합니다. 같은 보고서끼리만 비교합니다.
- 결측 연도를 0으로 채우지 않으며, 차입금 매핑이 불완전하면 지표를 비우고 관리 단계 판정을 보류합니다.
- 연간 3년 연속 이자보상배율 1배 미만은 "한계기업 참고조건"이며 공식·법적 분류가 아닙니다.

---

## 7. 3사 주요 지표 (`metrics.csv`)

| 기간 | 영업이익률 (롯데 / 대한 / 금호) | 이자보상배율† (배) | 부채비율 | ROE |
|---|---|---|---|---|
| 2021 | 8.47 / 7.13 / 28.44 | 6.01 / 18.08 / 41.31 | 48.01 / 22.16 / 59.67 | 9.87 / 7.64 / 47.76 |
| 2022 | -3.42 / -9.66 / 14.39 | -1.06 / -18.00 / 10.98 | 55.14 / 17.93 / 36.54 | 0.43 / -7.66 / 19.11 |
| 2023 | -1.74 / -2.49 / 5.68 | -0.47 / -3.04 / 5.95 | 65.46 / 20.37 / 36.78 | -0.33 / -1.58 / 7.77 |
| 2024 | -4.38 / -2.14 / 3.81 | -1.11 / -2.82 / 3.92 | 72.87 / 22.80 / 38.03 | -11.44 / -0.47 / 5.88 |
| 2025 | -5.10 / 1.57 / 3.93 | -1.09 / 2.10 / 3.87 | 76.52 / 29.73 / 35.67 | -15.13 / 1.74 / 4.74 |
| 2026H1 | 1.72 / 3.86 / 9.84 | 0.44 / 4.19 / 12.28 | 76.76 / 35.58 / 34.40 | 4.03 / 4.95 / 11.76 (연환산) |

매출 성장률·ROA·차입금 의존도를 포함한 전체 값은 `data/processed/metrics.csv`, 기업 비교는 `company_comparison.csv`에 있습니다.

---

## 8. 제출 결과물 위치

| 요구 결과물 | 경로 |
|---|---|
| Python 소스 파일 | `source/*.py`, `app/*.py` |
| DART 수집 원본 데이터 | `data/raw/*.json` (분석 3사 21개 포함 317개), `data/raw/collect_log.csv`, `corp_codes.csv`, `data/raw/audit/` |
| 정제 재무 데이터 | `data/processed/financials_clean.csv`, `account_mapping.csv` |
| 주요 재무지표 데이터 | `data/processed/metrics.csv`, `quarterly_metrics.csv` |
| 기업 비교 데이터 | `data/processed/company_comparison.csv`, `q2_reconciliation.csv` |
| 경영성과 비교 차트 | `output/charts/*.png` (매출 성장률, 영업이익률, 이자보상배율†, 차입금 의존도, 여신 관리 지도, 안정성, 분기 비교) |
| Streamlit 실행 소스 | `app/app.py` (+ `app/candidates/app_minji.py`, 화면 모듈) |
| Streamlit 실행 화면 | `output/streamlit_screen.png`, 탭별 `output/app_screens/` |
| 분석 결과 요약 보고서 | `report/분석결과_요약보고서.pdf` |
| 발표 PPT | `presentation/미니프로젝트04_발표자료.pptx` |
| 발표 영상 (AI 음성, 시연 포함) | `video/미니프로젝트04_발표영상_v1.mp4` (+ 자막 `.srt`) |
| 시연 영상 | `video/미니프로젝트04_시연영상_v1.mp4` (+ 자막 `.srt`) |
| API 명세서 | `API_명세서_v1.md` |
| README / requirements / 환경변수 예시 | `README.md`, `requirements.txt`, `.env.example` |

### 그 밖의 데이터 파일

| 경로 | 내용 |
|---|---|
| `data/processed/events.csv` | 출처가 확인된 이벤트(재무특약·신용보강·사업재편·연결 편입) |
| `data/processed/review_checklist.csv` | 주석·산업 확인 항목. 수기 정리, 모든 줄에 DART 접수번호 또는 기관 자료 출처. 계기판 수치와 분리 |
| `data/processed/data_quality.csv`, `check_log.csv` | 판정 가능 여부·누락·원문 링크, 검증 기록 |
| `data/processed/company_registry.csv`, `collection_coverage.csv` | 기업 목록·근거, 수집 상태·연결/별도 |
| `data/processed/audit_*.csv`, `verified_*.json/csv` | 공시 원문(감사보고서)에서 추출·검증한 값 (`AUDIT_DATA_GUIDE.md` 참고) |

---

## 9. 발표·시연 영상과 API 명세서

### 9-1. 영상 (`video/`)

| 파일 | 길이 | 내용 |
|---|---|---|
| `미니프로젝트04_발표영상_v1.mp4` | 18분 51초 | 발표자료 32장 + AI 음성 내레이션. **28번 슬라이드(14:19) 뒤 14:29~17:19에 앱 시연이 이어서 나옵니다** |
| `미니프로젝트04_시연영상_v1.mp4` | 2분 50초 | Streamlit 앱 시연만 따로 (롯데케미칼 만기연장 요청 상황) |
| `*.srt` | - | 한국어 자막. 영상 안에도 끄고 켤 수 있는 자막 트랙으로 들어 있음 |
| `영상_내레이션_원고_v1.md` | - | 내레이션 전문, 슬라이드별 시작 시각, 사용한 음성 |

- **보는 방법**: 파일을 더블클릭하면 기본 플레이어(Windows 미디어 플레이어·영화 및 TV, macOS QuickTime)로 재생됩니다. 1920x1080, H.264/AAC라 별도 코덱이 필요 없습니다.
- **자막 켜기**: QuickTime은 `보기 → 자막 → 한국어`, VLC는 `자막 → 하위 트랙`. 자막이 안 보이는 플레이어는 같은 이름의 `.srt`를 영상과 같은 폴더에 두고 열면 자동으로 붙습니다.
- **시연 순서** (발표 영상 14:29부터, 시연 영상 0:00부터): 사용 안내 → 여신 계기판·3초 요약 → 여신 관리 지도(롯데케미칼 궤적) → 실제 사례 카드(회사채 재무특약) → 대한유화 2022년 충격 시나리오(4.19배 → -5.01배, 정상 관리 → 관리 강화) → 롯데케미칼 주석·산업 확인 → 근거 지표 탭 → 심사 메모.
- **만든 방법**: 음성은 Microsoft Edge 신경망 TTS(`edge-tts`, 발표 `ko-KR-InJoonNeural`, 시연 `ko-KR-SunHiNeural`), 슬라이드는 PPT를 이미지로 내보내 사용, 시연은 이 ZIP의 앱을 `streamlit run app/app.py`로 실행해 실제로 조작한 화면을 녹화했습니다. 화면 속 숫자는 모두 `data/processed/` CSV 값입니다.

### 9-2. API 명세서 (`API_명세서_v1.md`)

| 장 | 내용 |
|---|---|
| 1. 공통 사항 | 키 저장·노출 방지 규칙, 타임아웃, 캐시 |
| 2. OpenDART | `corpCode.xml`, `fnlttSinglAcntAll.json`(요청 파라미터·응답 필드·저장 규칙), `company.json`, `list.json`, `document.xml`, 상태 코드별 처리 |
| 3. OpenAI | 챗봇 `POST /v1/responses` 요청 본문, 응답 숫자 검증 |
| 4. 내부 인터페이스 | `update_company()`, `answer_question()` 라우팅, 스크립트 명령 |
| 5. 데이터 파일 | `metrics.csv` 열 정의와 예시, 그 밖의 CSV 열 목록 |
| 6. 오류 처리 원칙 | 결측 ≠ 0, 연결 실패와 미제공 구분, 키 미출력 |

---

## 10. 확장 기능 (분석 결론에는 미사용)

보고서·PPT의 모든 분석과 숫자는 **3사 기준**입니다. 앱은 같은 기준으로 다른 정유·석유화학 공시기업도 비교해 볼 수 있습니다.

- 기본 목록 45개 기업, 업종 확인 대기 후보 19개. 기본 화면은 API 재무 데이터가 있는 32개 기업 표시(29개는 2026H1 포함).
- 후보 포함 API 원본 317건, 공시 원문 ZIP 43건, 재무 데이터 64개 기업, 연간·반기 지표 313행, 분기 지표 288행.
- 조회 기준: 2022-01-01~2026-09-30 사업보고서 제출기업 중 DART 업종 192*, 20111, 20119, 202* + 한국화학산업협회 회원사·정유 복합기업. **국내 전체 기업 전수 확인은 미완료**입니다.
- API가 `013(미제공)`인 13개 기업은 사이드바 `공시 원문 · 연간` 경로에서 핵심 수치를 조회할 수 있습니다.
- 모회사·자회사·복합기업의 연결 실적을 합산하거나 같은 사업부 실적으로 해석하지 마세요.

---

## 11. API 키와 보안

- 실제 키는 **코드·제출 ZIP·채팅 어디에도 넣지 않습니다.** 이 ZIP에는 `.env`가 없고 `.env.example`만 있습니다.
- `.env.example` 내용: `DART_API_KEY=YOUR_API_KEY`, `OPENAI_API_KEY=YOUR_API_KEY`
- 키는 프로젝트 루트 `.env`(또는 환경변수, `.streamlit/secrets.toml`)에서만 읽으며, 점검 기능도 키 값은 출력하지 않습니다.
- DART 키는 재수집·업데이트에만, OpenAI 키는 챗봇 자유 질문에만 필요합니다. 키가 없어도 앱의 모든 분석 화면은 정상 동작합니다.
- `.gitignore`에 `.env`, `.streamlit/secrets.toml`이 포함되어 있습니다.

---

## 12. 한계

- 중간재무제표(1분기·반기)는 감사가 아닌 검토 대상이며, 분기 실적은 재고평가·환율 등 일회성·계절성에 흔들립니다.
- 이자보상배율†은 금융원가 기준이라 실제 이자 부담과 다를 수 있습니다.
- 지분법 대상 합작사(예: HD현대케미칼)의 차입금은 연결 재무제표에 잡히지 않습니다.
- 관리 단계·기준선은 분석용 참고값이며 실제 은행의 여신 심사 기준이 아닙니다.

## 13. 공식 출처

[OpenDART 공시검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001) · [기업개황](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002) · [단일회사 전체 재무제표](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020) · [한국화학산업협회 회원사](https://kcia.kr/member-company-information/about-member-companies/member-company)
