"""주석·산업 확인: data/processed/review_checklist.csv(수기 정리 + 출처)를 읽어 보여주기만 한다.

원칙 (조윤호 「앱 구현 방향 v1」)
- metrics.csv와 계기판 기준(1배·30%)은 바꾸지 않는다. 이 화면은 숫자 신호와 분리된 정성 정보다.
- 모든 줄에 출처를 붙인다. 접수번호가 있으면 DART 원문 링크를 단다.
- 판단은 사람이 한다. 앱은 점수·등급·대출 가부를 만들지 않는다.
- CSV에 없는 기간·회사는 "확인 전"으로 두고 숫자를 지어 채우지 않는다.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data" / "processed"
PATH = DATA / "review_checklist.csv"
COMMON = "공통"
FLAG_STYLE = {  # 주의 = 빨강, 참고 = 회색, 양호 = 파랑
    "주의": ("#C92A2A", "#FFE3E3"),
    "참고": ("#495057", "#F1F3F5"),
    "양호": ("#1864AB", "#E7F5FF"),
}
DART_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"
# KPI 카드 툴팁에 붙일 항목: 지표 → 관련 주석·산업 분류
KPI_LINKS = {
    "sales_growth": ["종속기업"],
    "op_margin": ["업황·스프레드"],
    "roa": ["손상"],
    "roe": ["손상"],
    "debt_ratio": ["차입금", "담보·약정"],
    "icr": ["담보·약정"],
    "borrow_dep": ["차입금", "신용평가"],
}
FOOTER = "주석·산업 항목은 공시 원문·기관 자료를 사람이 대조해 수기 정리한 값 · 참고용이며 실제 은행 심사 기준이 아님 · 투자 권유 아님"


@st.cache_data(show_spinner=False, ttl=5)
def load_review(_mtime: float = 0.0) -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(PATH, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    for col in ["corp_name", "period", "category", "item", "finding", "status", "flag",
                "rcept_no", "note_ref", "source_url", "reviewer", "reviewed_at"]:
        if col not in df.columns:
            df[col] = ""
    df["step"] = df["category"].map(lambda c: "산업" if c.strip() == "산업" else "주석")
    return df


def _rows(corp: str, period: str) -> pd.DataFrame:
    df = load_review(PATH.stat().st_mtime if PATH.exists() else 0.0)
    if df.empty:
        return df
    return df[df.corp_name.isin([corp, COMMON]) & (df.period == str(period))]


def _first_sentence(text: str, limit: int = 120) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = re.split(r"(?<=\.)\s", text, maxsplit=1)[0]
    return cut if len(cut) <= limit + 40 else text[:limit].rstrip() + "…"


def _badge(flag: str, status: str) -> str:
    if status.strip() != "확인 완료":
        return '<span class="rv-badge" style="color:#868E96;background:#F1F3F5">확인 전</span>'
    color, bg = FLAG_STYLE.get(flag.strip(), FLAG_STYLE["참고"])
    label = flag.strip() or "참고"
    return f'<span class="rv-badge" style="color:{color};background:{bg}">{escape(label)}</span>'


def _source(r: pd.Series) -> str:
    parts = []
    if r["note_ref"]:
        parts.append("출처: " + r["note_ref"])
    if r["rcept_no"]:
        parts.append(f"[DART 원문 {r['rcept_no']}]({DART_URL.format(r['rcept_no'])})")
    if r["source_url"]:
        parts.append(f"[링크]({r['source_url']})")
    if r["reviewer"]:
        parts.append(f"기록 {r['reviewer']} {r['reviewed_at']}".strip())
    return " · ".join(parts) if parts else "출처 미기재"


def _card(r: pd.Series, key: str) -> None:
    with st.container(border=True):
        corp_tag = " · 3사 공통" if r["corp_name"] == COMMON else ""
        st.markdown(
            f'{_badge(r["flag"], r["status"])} <span class="rv-cat">{escape(r["category"])}</span> '
            f'<b>{escape(r["item"])}</b><span class="rv-cat">{corp_tag}</span>',
            unsafe_allow_html=True,
        )
        if not r["finding"].strip():
            st.caption("확인 전: 아직 원문 대조 내용이 없습니다.")
        else:
            short = _first_sentence(r["finding"])
            st.markdown(escape(short).replace("$", "\\$").replace("[", "<b>[").replace("]", "]</b>"), unsafe_allow_html=True)
            if short != r["finding"].strip():
                with st.expander("전체 내용", expanded=False):
                    st.markdown(escape(r["finding"]).replace("$", "\\$"))
        st.caption(_source(r))


def render_review(corp: str, period: str) -> None:
    """은행 판단 탭, 심사 메모 바로 위. 왼쪽 주석 / 오른쪽 산업."""
    st.markdown(
        "<style>.rv-badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:800;"
        "margin-right:4px}.rv-cat{color:#868E96;font-size:12.5px;margin:0 4px}</style>",
        unsafe_allow_html=True,
    )
    st.subheader(f"주석·산업 확인 · {corp}")
    st.caption("심사 순서: 숫자(계기판) → 주석(차입금·손상·약정) → 산업(업황·신용평가). 숫자 신호와 섞지 않고 따로 봅니다.")
    rows = _rows(corp, period)
    if rows.empty:
        st.info(f"확인 전: {corp}의 {period} 기준으로 정리된 주석·산업 항목이 없습니다. "
                "현재 review_checklist.csv는 2026H1 기준으로 정리되어 있습니다.")
        st.caption(FOOTER)
        return
    done = rows[rows.status.str.strip() == "확인 완료"]
    counts = done.flag.str.strip().replace("", "참고").value_counts()
    pending = len(rows) - len(done)
    st.markdown(
        " ".join(f'{_badge(k, "확인 완료")} {counts.get(k, 0)}건' for k in ["주의", "참고", "양호"] if counts.get(k, 0))
        + (f' {_badge("", "미확인")} {pending}건' if pending else ""),
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    order = {"주의": 0, "참고": 1, "양호": 2}
    for col, step in [(left, "주석"), (right, "산업")]:
        with col:
            st.markdown(f"**{step}**" + (" · 공시 주석" if step == "주석" else " · 신용평가·업황·정책"))
            part = rows[rows.step == step].copy()
            if part.empty:
                st.caption("확인 전")
                continue
            part["_o"] = part.flag.str.strip().map(order).fillna(1)
            for i, (_, r) in enumerate(part.sort_values(["_o"], kind="stable").iterrows()):
                _card(r, f"{step}_{i}")
    st.caption(FOOTER)


def kpi_hint(corp: str, period: str, field: str) -> str:
    """KPI 카드 help= 에 덧붙일 한 줄. 관련 항목이 없으면 빈 문자열."""
    cats = KPI_LINKS.get(field)
    if not cats:
        return ""
    rows = _rows(corp, period)
    if rows.empty:
        return ""
    hit = rows[(rows.status.str.strip() == "확인 완료")
               & (rows.category.isin(cats) | rows["item"].isin(cats))
               & (rows.corp_name == corp)]
    if hit.empty:
        return ""
    r = hit.iloc[0]
    return f"\n\n주석·산업 확인 ({r['item']}): {_first_sentence(r['finding'], 110)} [{r['note_ref']}]"


def render_industry_strip(period: str) -> None:
    """충격 분기 탭: 3사 공통 산업 항목(원료 조달·스프레드)을 같은 형식으로."""
    rows = _rows("__none__", period)
    rows = rows[(rows.corp_name == COMMON) & (rows.step == "산업")]
    if rows.empty:
        return
    st.subheader("산업 확인 · 원료 조달과 스프레드")
    st.caption("재무제표가 버텨도 원료 조달·스프레드가 먼저 흔들릴 수 있어 비재무 항목으로 따로 봅니다.")
    cols = st.columns(len(rows)) if len(rows) <= 3 else st.columns(3)
    for i, (_, r) in enumerate(rows.iterrows()):
        with cols[i % len(cols)]:
            _card(r, f"strip_{i}")
    st.caption(FOOTER)
