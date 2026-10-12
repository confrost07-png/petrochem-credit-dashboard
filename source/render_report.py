"""검증된 metrics.csv · quarterly_metrics.csv로 분석결과 요약보고서 PDF(v2)를 만든다.

실행: python source/render_charts.py && python source/render_report.py
- 분석 대상은 석유화학 3사(롯데케미칼·대한유화·금호석유화학)다. 확장 기업 행은 읽지 않는다.
- 모든 숫자는 CSV에서 계산해 넣는다. 본문에 숫자를 손으로 적지 않는다.
- 반올림은 사사오입(엑셀과 같음)이다.
"""
from __future__ import annotations  # 파이썬 3.9에서도 X | None 표기 허용

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
CHARTS = ROOT / "output" / "charts"
OUT = ROOT / "report" / "분석결과_요약보고서.pdf"
CORPS = ["롯데케미칼", "대한유화", "금호석유화학"]
CODES = {"롯데케미칼": "011170", "대한유화": "006650", "금호석유화학": "011780"}
YEARS = ["2021", "2022", "2023", "2024", "2025"]
PERIODS = YEARS + ["2026H1"]
NAVY = colors.HexColor("#102B55")
BLUE = colors.HexColor("#2455A4")
RED = colors.HexColor("#C63838")
PALE = colors.HexColor("#EDF3FB")
GRAY = colors.HexColor("#52657D")
STAGE_COLOR = {"집중 관리": "#FFE3E3", "관리 강화": "#FFF4E6", "관찰": "#FFF9DB", "정상 관리": "#EBFBEE", "판정 보류": "#F1F3F5"}


# ---------- 글꼴·숫자 ----------
def korean_font() -> tuple[str, str]:
    """(본문, 굵게) 글꼴 이름. Windows 맑은 고딕, 리눅스·코랩 나눔고딕, macOS 애플고딕."""
    pairs = [
        (Path("C:/Windows/Fonts/malgun.ttf"), Path("C:/Windows/Fonts/malgunbd.ttf")),
        (Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"), Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")),
        (Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"), Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf")),
    ]
    for regular, bold in pairs:
        if regular.exists():
            pdfmetrics.registerFont(TTFont("KR", str(regular)))
            pdfmetrics.registerFont(TTFont("KRB", str(bold if bold.exists() else regular)))
            return "KR", "KRB"
    raise RuntimeError("한글 글꼴이 없습니다. 코랩·리눅스: apt-get install fonts-nanum")


def rnd(value: object, digits: int = 1) -> str:
    """사사오입 문자열. 결측은 '-'."""
    if value is None or pd.isna(value):
        return "-"
    q = Decimal(1).scaleb(-digits)
    return str(Decimal(str(float(value))).quantize(q, rounding=ROUND_HALF_UP))


def pct(value: object, digits: int = 2) -> str:
    return "-" if pd.isna(value) else rnd(value, digits) + "%"


def times(value: object, digits: int = 2) -> str:
    return "-" if pd.isna(value) else rnd(value, digits) + "배"


def eok(value: object) -> str:
    return "-" if pd.isna(value) else f"{int(Decimal(str(float(value) / 1e8)).quantize(Decimal(1), rounding=ROUND_HALF_UP)):,}억원"


def jo(value: object) -> str:
    return "-" if pd.isna(value) else rnd(float(value) / 1e12, 2) + "조원"


def growth(a: float, b: float) -> str:
    """a → b 변화율(%)."""
    return "-" if (pd.isna(a) or pd.isna(b) or a == 0) else rnd((b / a - 1) * 100, 1) + "%"


def stage(icr: float, borrow: float, line: float = 30.0) -> str:
    """선 2개(이자보상배율 1배, 차입금 의존도 30%)로 나눈 관리 단계. 참고용."""
    if pd.isna(icr) or pd.isna(borrow):
        return "판정 보류"
    if icr < 1 and borrow >= line:
        return "집중 관리"
    if icr < 1:
        return "관리 강화"
    if borrow >= line:
        return "관찰"
    return "정상 관리"


def longest_run_below_one(series: pd.Series) -> tuple[int, str]:
    best, run, start, best_span = 0, 0, None, ""
    for year, value in series.items():
        if pd.notna(value) and value < 1:
            run += 1
            start = year if run == 1 else start
            if run > best:
                best, best_span = run, f"{start}~{year}"
        else:
            run = 0
    return best, best_span


# ---------- 레이아웃 도우미 ----------
def table(rows: list[list], widths: list[float], font: str, bold: str, size: float = 8.2,
          extra: list | None = None) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font), ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTSIZE", (0, 0), (-1, -1), size),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, -1), (-1, -1), .5, colors.HexColor("#CDD9E8")),
    ]
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def chart(name: str, width: float = 170 * mm) -> Image:
    path = CHARTS / name
    if not path.exists():
        raise FileNotFoundError(f"차트가 없습니다: {path}. source/render_charts.py를 먼저 실행하세요.")
    with PILImage.open(path) as bitmap:
        w, h = bitmap.size
    return Image(str(path), width=width, height=width * h / w)


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("KR", 7.5)
    canvas.setFillColor(GRAY)
    canvas.drawString(15 * mm, 9 * mm, "MODULE04 미니프로젝트04 · 2조 | OpenDART 연결재무제표 | 참고용이며 실제 은행 심사 기준이 아님 | 투자 권유 아님")
    canvas.drawRightString(195 * mm, 9 * mm, str(doc.page))
    canvas.restoreState()


# ---------- 본문 ----------
def main() -> None:
    if (DATA / ".sample_data").exists():
        raise SystemExit("가상 데이터로 보고서를 만들 수 없습니다.")
    font, bold = korean_font()
    m = pd.read_csv(DATA / "metrics.csv", dtype={"period": str, "stock_code": str})
    q = pd.read_csv(DATA / "quarterly_metrics.csv", dtype={"period": str, "stock_code": str})
    m = m[m.corp_name.isin(CORPS) & m.period.isin(PERIODS)]
    q = q[q.corp_name.isin(CORPS)]
    if len(m) != 18:
        raise ValueError(f"3사 × 6기간 = 18행이어야 합니다 (현재 {len(m)}행). validate_data.py를 먼저 실행하세요.")
    M = {c: m[m.corp_name == c].set_index("period").reindex(PERIODS) for c in CORPS}
    Q = {c: q[q.corp_name == c].set_index("period") for c in CORPS}

    st = {
        "title": ParagraphStyle("t", fontName=bold, fontSize=20, leading=27, textColor=NAVY, spaceAfter=4),
        "sub": ParagraphStyle("s", fontName=font, fontSize=9.5, leading=14, textColor=GRAY, spaceAfter=10),
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=13.5, leading=19, textColor=NAVY, spaceBefore=10, spaceAfter=5),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=10.5, leading=15, textColor=BLUE, spaceBefore=6, spaceAfter=3),
        "body": ParagraphStyle("b", fontName=font, fontSize=9.3, leading=14.6, spaceAfter=5),
        "note": ParagraphStyle("n", fontName=font, fontSize=7.8, leading=11.5, textColor=GRAY, spaceAfter=6),
        "box": ParagraphStyle("x", fontName=font, fontSize=9.3, leading=14.6),
    }
    P = lambda text, s="body": Paragraph(text, st[s])  # noqa: E731
    story = []

    # 계산해 둘 값
    loss_years = {c: int((M[c].loc[YEARS, "op_income"] < 0).sum()) for c in CORPS}
    runs = {c: longest_run_below_one(M[c].loc[YEARS, "icr"]) for c in CORPS}
    stages = {c: {p: stage(M[c].loc[p, "icr"], M[c].loc[p, "borrow_dep"]) for p in PERIODS} for c in CORPS}
    L = M["롯데케미칼"]
    lotte_ratio = {y: L.loc[y, "net_income"] / L.loc[y, "op_income"] for y in ["2024", "2025"]}

    # 표지·요약
    story += [P("석유화학 3사 재무제표 기반 경영성과 분석", "title"),
              P("불황 4년, 은행은 누구의 빚을 걱정하고 이미 빌려준 돈은 어떻게 지켜야 하나 | 분석 범위 2021~2025 사업연도 + 2026년 상반기 누적 "
                "(심화: 2025·2026 1·2분기) | 연결재무제표 | 출처 OpenDART", "sub")]
    summary = [
        f"<b>1. 불황에서 갈린 건 규모가 아니라 적자 여부였다.</b> 2021~2025년 영업적자 연도는 롯데케미칼 {loss_years['롯데케미칼']}년, "
        f"대한유화 {loss_years['대한유화']}년, 금호석유화학 {loss_years['금호석유화학']}년이다.",
        f"<b>2. 부채비율보다 이자보상배율이 위험을 먼저 보였다.</b> 2022~2024년 부채비율이 3사 중 가장 낮았던 대한유화도 같은 기간 "
        f"이자보상배율† 1배 미만이 {runs['대한유화'][0]}년({runs['대한유화'][1]}) 이어졌다.",
        f"<b>3. 2026년 상반기 흑자는 2분기에 갈렸다.</b> 상반기 누적으로는 3사 모두 영업흑자지만, 2분기 단독 영업이익률은 "
        f"대한유화 {pct(Q['대한유화'].loc['2026Q2', 'op_margin'])}로 다시 적자였고 롯데케미칼은 흑자에도 이자보상배율† "
        f"{times(Q['롯데케미칼'].loc['2026Q2', 'icr'])}였다.",
    ]
    box = Table([[P("<br/>".join(summary), "box")]], colWidths=[180 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), .6, BLUE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                             ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [box, P("† 3사 모두 손익계산서 본문에 이자비용 단독 계정이 없어 이자보상배율은 영업이익 ÷ 금융원가로 계산했다. "
                     "금융원가에는 외환·파생 손실이 섞일 수 있어 실제 이자 기준보다 낮게 나올 수 있다.", "note")]

    # 1. 기업 선정
    story += [P("1. 기업 선정 이유", "h1"),
              P("석유화학 업종은 2022년 이후 중국 증설에 따른 공급과잉으로 업황이 꺾였고, 은행권이 실제로 업종 여신을 관리 대상으로 다루기 시작했다"
                "(2024년 회사채 재무약정 미준수에 따른 신용보강, 2025년 채권단 자율협약, 2026년 사업재편 승인). "
                "그래서 \"같은 불황에서 누가 이자를 감당하며 버티나\"를 재무제표로 묻기에 적합하다."),
              P("석유화학 상장사 12곳에서 관문 4개(① 2021~2026.06 공시가 모두 있는 상장사 ② 석유화학이 주력 사업 ③ 나프타 계열 원료 "
                "④ 자본잠식 같은 극단값 없이 지표 계산 가능)를 통과한 3사를 골랐다. 3사는 규모와 제품 구성이 달라 두 가지 비교가 가능하다."),
              table([["기업", "종목코드", "규모·구조", "비교 역할"],
                     ["롯데케미칼", "011170", "대형 · 범용 NCC", "규모가 크면 버티나 (대한유화와 비교)"],
                     ["대한유화", "006650", "중형 · 범용 NCC", "같은 범용 제품, 작은 규모"],
                     ["금호석유화학", "011780", "합성고무 · 특수제품", "제품 구성이 다르면 덜 흔들리나"]],
                    [30 * mm, 22 * mm, 45 * mm, 83 * mm], font, bold),
              P("※ 앱은 같은 기준으로 다른 정유·석유화학 공시기업도 비교할 수 있게 확장했지만, 본 보고서의 분석과 결론은 위 3사만 대상으로 한다.", "note")]

    # 2. 데이터 수집
    story += [P("2. 데이터 수집", "h1"),
              P("OpenDART 고유번호 목록(corpCode.xml)으로 3사의 고유번호를 확인한 뒤, 단일회사 전체 재무제표 API(fnlttSinglAcntAll)를 "
                "총 21회 호출했다: 사업보고서(11011) 3사 × 2021~2025년 15회, 반기보고서(11012) 2026년 3회, 1분기보고서(11013) 2026년 3회. "
                "모두 연결재무제표(fs_div=CFS)이며, 원본 응답은 data/raw에 수정 없이 보관하고 수집 로그를 남겼다. "
                "새 폴더에서 원본만으로 정제·지표를 다시 만들어도(source/rebuild.py) 3사 수치가 동일하게 재현된다.")]

    # 3. 재무제표 정리
    story += [P("3. 재무제표 정리", "h1"),
              P("손익계산서에서 매출액·영업이익·연결 당기순이익·지배기업 소유주 귀속 순이익·금융원가를, 재무상태표에서 자산·부채·자본·지배기업 "
                "소유주지분·차입금을 계정 ID 우선으로 추출하고 매핑 근거를 data/processed/account_mapping.csv에 남겼다. 주요 정리 규칙은 다음과 같다."),
              table([["항목", "우리 조 기준", "이유"],
                     ["연결 vs 별도", "연결", "은행은 그룹 전체의 상환 능력을 본다"],
                     ["이자비용", "본문에 없으면 금융원가로 대체, †표시", "3사 모두 이자비용 단독 계정 없음"],
                     ["차입금", "단기 + 유동성장기 + 장기 + 사채, 리스부채 제외", "이자가 붙는 빚만, 3사 같은 범위"],
                     ["연간 ROA·ROE 분모", "평균 잔액 (기초 + 기말) ÷ 2", "1년 동안 실제로 쓴 규모"],
                     ["2026 상반기", "매출 성장률은 전년 동기 대비, ROA·ROE는 연환산", "반기 값을 연간과 섞지 않음"],
                     ["결측", "0으로 채우지 않음", "가짜 급등·급락 방지"]],
                    [33 * mm, 77 * mm, 70 * mm], font, bold)]

    # 4. 주요 재무지표
    rows = [["기업 · 지표", "2021", "2022", "2023", "2024", "2025", "26 상반기"]]
    for c in CORPS:
        for key, name in [("sales_growth", "매출 성장률"), ("op_margin", "영업이익률"), ("debt_ratio", "부채비율"),
                          ("roa", "ROA"), ("roe", "ROE")]:
            rows.append([f"{c} {name}"] + [rnd(M[c].loc[p, key], 2) for p in PERIODS])
    neg = [("TEXTCOLOR", (j, i), (j, i), RED) for i, r in enumerate(rows[1:], 1) for j, v in enumerate(r[1:], 1)
           if v.startswith("-") and v != "-"]
    story += [PageBreak(), P("4. 주요 재무지표", "h1"),
              P("과제 필수 지표 5개를 3사 × 6기간으로 계산했다(단위 %, 빨간 글씨는 음수). 2026 상반기 매출 성장률은 전년 상반기 대비, ROA·ROE는 "
                "반기 순이익 × 2 ÷ 6월 말 잔액(연환산)이다. ROA 분자는 연결 순이익, ROE 분자는 지배주주 순이익이다."),
              table(rows, [44 * mm] + [22.6 * mm] * 6, font, bold, 7.8, neg),
              P("보조 지표: 이자보상배율† = 영업이익 ÷ 금융원가(1배 참고선, 연간 3년 연속 1배 미만이면 한국은행 한계기업 정의에 해당하는 수준), "
                "차입금 의존도 = 차입금 ÷ 자산총계(30% 참고선, 은행마다 다름).", "note")]

    # 5. 성장성
    gtext = []
    for c in CORPS:
        gtext.append(f"{c}: 매출 {jo(M[c].loc['2021', 'revenue'])} → {jo(M[c].loc['2025', 'revenue'])}"
                     f"(2021 → 2025 {growth(M[c].loc['2021', 'revenue'], M[c].loc['2025', 'revenue'])}), "
                     f"2026 상반기는 전년 동기 대비 {pct(M[c].loc['2026H1', 'sales_growth'])}")
    story += [P("5. 성장성 분석", "h1"), P("<br/>".join(gtext)),
              P("매출 성장률은 2021년 3사 모두 크게 올랐다가 2022년 이후 회사마다 방향이 엇갈렸다. 석유화학 매출은 나프타·유가에 연동된 판가 효과가 커서 "
                "매출이 늘어도 \"많이 판 것\"이 아니라 \"비싸게 판 것\"일 수 있다. 그래서 성장성은 다음 장의 이익률과 함께 읽는다."),
              chart("sales_growth.png", 165 * mm)]

    # 6. 수익성
    story += [P("6. 수익성 분석", "h1"),
              P(f"영업이익률이 0 아래로 내려간 연도는 롯데케미칼 {loss_years['롯데케미칼']}년(2022~2025), 대한유화 {loss_years['대한유화']}년(2022~2024), "
                f"금호석유화학 {loss_years['금호석유화학']}년이다. 금호석유화학은 2021년 {pct(M['금호석유화학'].loc['2021', 'op_margin'])}에서 "
                f"2025년 {pct(M['금호석유화학'].loc['2025', 'op_margin'])}로 크게 낮아졌지만 흑자를 유지했다. "
                "\"하락 폭이 큰가\"로 물으면 금호의 하락 폭이 가장 커서 가설 1(범용 2사의 하락 폭이 더 크다)은 기각되고, \"적자로 떨어졌나\"로 물으면 3사가 뚜렷이 갈린다."),
              P(f"롯데케미칼은 영업 밖 손실도 컸다. 2024년 영업손실 {eok(L.loc['2024', 'op_income'])}에 연결 순손실 {eok(L.loc['2024', 'net_income'])}"
                f"({rnd(lotte_ratio['2024'], 1)}배), 2025년 영업손실 {eok(L.loc['2025', 'op_income'])}에 순손실 {eok(L.loc['2025', 'net_income'])}"
                f"({rnd(lotte_ratio['2025'], 1)}배)로, ROE가 {pct(L.loc['2024', 'roe'])}, {pct(L.loc['2025', 'roe'])}까지 내려갔다. "
                "손상 등 영업외 항목의 구체적 원인은 주석 확인이 필요하다(가설)."),
              chart("op_margin.png", 165 * mm)]

    # 7. 안정성
    bs_rows = [["기업 (조원)", "자산 2021", "자산 2025", "자산 26.06", "부채 2021", "부채 2025", "부채 26.06", "자본 26.06"]]
    for c in CORPS:
        bs_rows.append([c] + [rnd(M[c].loc[p, "assets"] / 1e12, 2) for p in ["2021", "2025", "2026H1"]]
                       + [rnd(M[c].loc[p, "liabilities"] / 1e12, 2) for p in ["2021", "2025", "2026H1"]]
                       + [rnd(M[c].loc["2026H1", "equity"] / 1e12, 2)])
    icr_rows = [["이자보상배율†"] + ["2021", "2022", "2023", "2024", "2025", "26 상반기"]]
    for c in CORPS:
        icr_rows.append([c] + [times(M[c].loc[p, "icr"]) for p in PERIODS])
    low = [("BACKGROUND", (j, i), (j, i), colors.HexColor("#FFE3E3")) for i, r in enumerate(icr_rows[1:], 1)
           for j, v in enumerate(r[1:], 1) if v != "-" and float(v.replace("배", "")) < 1]
    story += [PageBreak(), P("7. 안정성 분석", "h1"),
              P(f"자산·부채 규모: 롯데케미칼은 2021 → 2025년 자산 {growth(L.loc['2021', 'assets'], L.loc['2025', 'assets'])}, "
                f"부채 {growth(L.loc['2021', 'liabilities'], L.loc['2025', 'liabilities'])}로 적자 기간에 자산과 빚이 같이 커졌다. "
                f"자본총계 중 지배주주 몫은 {jo(L.loc['2021', 'equity_owner'])} → {jo(L.loc['2025', 'equity_owner'])}로 줄었다."),
              table(bs_rows, [30 * mm] + [21.4 * mm] * 7, font, bold, 7.8),
              Spacer(1, 4),
              P(f"부채비율만 보면 대한유화가 2022~2024년 3사 중 가장 낮았다({pct(M['대한유화'].loc['2022', 'debt_ratio'])}~"
                f"{pct(M['대한유화'].loc['2024', 'debt_ratio'])}). 그러나 같은 기간 이자보상배율†은 1배 미만이 {runs['대한유화'][0]}년 이어졌다. "
                f"롯데케미칼은 {runs['롯데케미칼'][1]} {runs['롯데케미칼'][0]}년 연속 1배 미만이고, 차입금 의존도가 "
                f"{pct(L.loc['2021', 'borrow_dep'])}(2021)에서 {pct(L.loc['2024', 'borrow_dep'])}(2024)로 30% 참고선을 넘었다. "
                f"대한유화의 차입금 의존도도 {pct(M['대한유화'].loc['2021', 'borrow_dep'])}에서 {pct(M['대한유화'].loc['2026H1', 'borrow_dep'])}(2026.06)로 꾸준히 올랐다."),
              table(icr_rows, [30 * mm] + [25 * mm] * 6, font, bold, 7.8, low),
              P("분홍 칸 = 1배 미만(영업이익으로 금융원가를 감당하지 못함). 대한유화 2022년의 큰 음수는 분모가 작아 커 보일 뿐 크기에 의미가 없다.", "note"),
              chart("borrow_dependence.png", 160 * mm)]

    # 8. 기업 비교
    srows = [["관리 단계(참고)"] + ["2021", "2022", "2023", "2024", "2025", "26 상반기"]]
    for c in CORPS:
        srows.append([c] + [stages[c][p] for p in PERIODS])
    scol = [("BACKGROUND", (j, i), (j, i), colors.HexColor(STAGE_COLOR[v])) for i, r in enumerate(srows[1:], 1)
            for j, v in enumerate(r[1:], 1)]
    story += [PageBreak(), P("8. 기업 비교: 관리 단계", "h1"),
              P("은행 심사역의 질문(Q1 돈을 벌고 있나, Q2 이자를 감당하나, Q3 빚이 늘고 있나)을 선 2개로 묶었다. 가로 기준은 이자보상배율† 1배, "
                "세로 기준은 차입금 의존도 30%다. 지표를 합산한 점수나 등급은 만들지 않고, \"왜 이 단계인가\"를 선 하나로 설명할 수 있게 했다. "
                "부채비율에는 기준선을 걸지 않았다. 영구채(회계상 자본)를 발행하면 갚을 부담은 그대로인데 부채비율만 내려가기 때문이다."),
              table(srows, [30 * mm] + [25 * mm] * 6, font, bold, 8, scol),
              Spacer(1, 4),
              P(f"롯데케미칼은 2021년 정상 관리 → 2022~2023년 관리 강화 → 2024년부터 집중 관리 칸으로 옮겨 갔다. 집중 관리로 넘어간 2024년은 "
                "회사채 재무약정 미준수와 4대 시중은행 신용보강이 있었던 해와 같다(같은 시기의 사실이며 인과를 단정하지 않는다). "
                f"대한유화는 2022~2024년 관리 강화 칸에 있다가 2025년 정상 관리로 돌아왔다. 금호석유화학은 6개 기간 모두 정상 관리다."),
              chart("credit_map.png", 165 * mm)]

    # 9. 심화: 2026 분기
    qrows = [["영업이익률 (2025 → 2026)", "1분기", "2분기 (충격 분기)", "상반기 누적"]]
    for c in CORPS:
        qq = Q[c]
        qrows.append([c, f"{pct(qq.loc['2025Q1', 'op_margin'])} → {pct(qq.loc['2026Q1', 'op_margin'])}",
                      f"{pct(qq.loc['2025Q2', 'op_margin'])} → {pct(qq.loc['2026Q2', 'op_margin'])}",
                      f"{pct(qq.loc['2025H1', 'op_margin'])} → {pct(qq.loc['2026H1', 'op_margin'])}"])
    brows = [["부채비율 / 차입금 의존도", "2025-12-31", "2026-03-31", "2026-06-30"]]
    for c in CORPS:
        qq = Q[c]
        brows.append([c, f"{pct(M[c].loc['2025', 'debt_ratio'])} / {pct(M[c].loc['2025', 'borrow_dep'])}",
                      f"{pct(qq.loc['2026Q1', 'debt_ratio'])} / {pct(qq.loc['2026Q1', 'borrow_dep'])}",
                      f"{pct(qq.loc['2026Q2', 'debt_ratio'])} / {pct(qq.loc['2026Q2', 'borrow_dep'])}"])
    story += [PageBreak(), P("9. 심화 분석: 2026 호르무즈 충격 분기", "h1"),
              P("2026년 2월 말 미국·이란 전쟁 이후 호르무즈 해협이 봉쇄되면서 나프타 가격이 t당 633달러(2/27)에서 1,089달러(3/24)로 약 72% 올랐다. "
                "1분기(1~3월)는 대부분 충격 이전이고, 2분기(4~6월)가 충격이 온전히 반영된 구간이다. 그래서 상반기 누적만 보지 않고 분기를 나눠 "
                "전년 같은 분기와 비교했다."),
              table(qrows, [45 * mm, 45 * mm, 45 * mm, 45 * mm], font, bold, 8),
              Spacer(1, 4),
              P(f"롯데케미칼은 1·2분기 모두 흑자였지만 2분기 이자보상배율†은 {times(Q['롯데케미칼'].loc['2026Q2', 'icr'])}로 아직 1배 아래다. "
                f"대한유화는 1분기 {pct(Q['대한유화'].loc['2026Q1', 'op_margin'])} 흑자 뒤 2분기 다시 적자였다. 금호석유화학은 1분기에 전년보다 낮아졌다가 "
                f"2분기 {pct(Q['금호석유화학'].loc['2026Q2', 'op_margin'])}로 급등했다. 원료가가 오를 때는 미리 싸게 사 둔 재고로 일시적 이익이 날 수 있어"
                "(래깅 효과), 흑자 전환이 이어지는지는 다음 분기 실적으로 확인해야 한다(가설)."),
              table(brows, [45 * mm, 45 * mm, 45 * mm, 45 * mm], font, bold, 8),
              P("2026년 1분기·반기 재무제표는 감사가 아닌 검토 대상이다. 분기 실적은 재고평가·환율 같은 일회성·계절성 요인에 크게 흔들린다. "
                "대산 1호 사업재편의 영구채 전환은 통합 법인 대상이라 6월 말 롯데케미칼 연결 재무상태표에는 반영되지 않았다.", "note"),
              chart("quarter_comparison.png", 160 * mm)]

    # 10. 인사이트 + 은행 대응
    story += [P("10. 주요 인사이트와 은행 관점의 시사점", "h1"),
              P("<b>① 매출 규모보다 \"적자 여부와 기간\"이 상환 능력을 가른다.</b> 같은 불황에서 금호석유화학은 영업이익률이 크게 낮아졌어도 1배 위를 지켰고, "
                "범용 NCC 2사는 3~4년 1배 아래로 내려갔다(제품 구성이 원인인지는 가설)."),
              P("<b>② 부채비율 하나로는 상환 위험을 놓친다.</b> 부채비율이 가장 낮던 대한유화도 이자 감당 신호는 3년 연속 나빴다. 신호등은 실제 상환 부담 지표인 "
                "이자보상배율†·차입금 의존도에 거는 것이 맞다."),
              P("<b>③ 흑자 전환만으로 여신 조건을 바로 풀지 않는다.</b> 2026년 상반기 흑자는 원료가 급등기의 일회성 요인이 섞였을 수 있어, 분기마다 재무 신호를 "
                "다시 확인하고 원료(나프타) 조달은 재무제표 밖 항목으로 따로 점검한다."),
              KeepTogether([table([["관리 단계", "은행이 검토할 대응", "실제 사례 (해당 기업)"],
                     ["정상 관리", "정기 점검, 업종 한도 점검", "-"],
                     ["관리 강화", "만기연장·이자유예·금리조정 조건 검토", "2025.09.30 17개 은행 채권단 자율협약 (업종 전체)"],
                     ["집중 관리", "담보·보증 보강, 사업재편 조건부 지원 검토", "2024.12 4대 시중은행 신용보강 (롯데케미칼),\n2026.02.23 대산 1호 사업재편 승인 (롯데케미칼·HD현대케미칼)"]],
                    [25 * mm, 62 * mm, 93 * mm], font, bold, 7.8)]),
              P("대응은 모두 \"검토\"이며 대출 가부 판단이 아니다. 2024년 롯데케미칼의 회사채 재무약정은 3개년 누적 EBITDA/이자비용 5배였고, 본 분석의 "
                "1배 참고선과는 지표·기준이 다르다.", "note")]

    # 11. 한계
    story += [P("11. 한계 및 개선 방향", "h1"),
              P("· 이자보상배율은 금융원가 기준이라 실제 이자 기준보다 낮게 나올 수 있다. 다음 단계에서 주석의 이자비용으로 바꿔 검증한다.<br/>"
                "· 연결재무제표 본문만으로는 사업부별(석유화학 vs 기타) 실적과 차입 만기·담보·재무약정을 알 수 없다. 주석을 읽어 \"심사역 확인\" 항목으로 보강한다.<br/>"
                "· 2026년 수치는 검토 재무제표이며 하반기 이후는 반영되지 않았다. 3분기 실적으로 흑자 지속 여부를 확인한다.<br/>"
                "· 관리 단계와 기준선(1배, 30%)은 참고용이며 실제 은행 심사 기준이 아니다. 투자 권유가 아니다.<br/>"
                "· 가설 판정: H1 이익률 하락 폭(기각, 질문을 적자 여부로 바꿈) · H2 롯데 빚·이자(지지) · H3 부채비율의 한계(부분 지지) · H4 신호 → 관리(데이터로 검정 불가, 사례로 설명)"),
              P("출처: 금융감독원 OpenDART 단일회사 전체 재무제표 API(3사 2021~2025 사업보고서, 2026 1분기·반기보고서) · 계산 근거 data/processed/metrics.csv, "
                "quarterly_metrics.csv, account_mapping.csv, check_log.csv · 사례: 비즈워치 2024-12-19(롯데케미칼 재무특약 조정·신용보강), "
                "한겨레 2025-09-30(석유화학 채권단 자율협약), 금융위원회 블로그 2026-02(대산 1호 사업재편 승인), 연합뉴스 2026-03-26(호르무즈 봉쇄와 나프타 가격).", "note")]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                            title="석유화학 3사 재무제표 기반 경영성과 분석", author="MODULE04 미니프로젝트04 2조")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"보고서 저장: {OUT}")


if __name__ == "__main__":
    main()
