"""차트 공통 스타일: 강조 기업만 색, 나머지는 회색 배경, 2026H1 점선·빈 마름모, 기준선 라벨, 축 잘림 표시.

원칙
- 한 차트에 색은 최대 5개(대상 기업 + 비교 기업 4개). 그 이상은 회색 얇은 선으로 맥락만 보여준다.
- 연간(2021~2025)은 실선, 2026 상반기는 점선과 빈 마름모로 구분하고 노란 띠로 표시한다.
- 연간과 반기 누적(2024H1·2025H1)을 한 추이에 섞지 않는다.
"""
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

FY = ["2021", "2022", "2023", "2024", "2025"]
H1 = "2026H1"
X_ORDER = FY + [H1]
X_LABEL = {**{p: p for p in FY}, H1: "2026 상반기"}

FIXED = {"롯데케미칼": "#B88400", "대한유화": "#5474C5", "금호석유화학": "#2D9184"}
EXTRA = ["#8A6BC4", "#C7738C", "#657E8B", "#BC714D", "#75864E"]
GRAY = "#C3CAD3"
INK, MUTED, GRID = "#302F35", "#7B7C86", "#F0F0F3"
RED, AMBER = "#C92A2A", "#B45309"
MAX_HIGHLIGHT = 5

# Shared presentation defaults for every Plotly chart, including source-report views.
pio.templates['financial_cards'] = go.layout.Template(layout=dict(
    paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF',
    font=dict(family='Noto Sans KR, Malgun Gothic, sans-serif', size=13, color=INK),
    colorway=list(FIXED.values()) + EXTRA,
    hoverlabel=dict(bgcolor='#29292F', bordercolor='#29292F', font=dict(color='#FFFFFF',size=13)),
    xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color=MUTED), automargin=True),
    yaxis=dict(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), automargin=True),
    legend=dict(bgcolor='rgba(0,0,0,0)',font=dict(size=12,color=MUTED)),
))
pio.templates.default = 'financial_cards'


def num(x, nd=1, sign=False):
    """사사오입 표시 (엑셀과 같은 결과)."""
    if x is None or pd.isna(x):
        return "-"
    d = Decimal(str(round(float(x), 6))).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    if d == 0:
        d = abs(d)
    s = f"{d:,}"
    return ("+" + s) if sign and d > 0 else s


def palette(companies):
    """강조 기업 -> 색. 3사는 고정색, 나머지는 선택 순서대로. 5개를 넘는 기업은 None(회색)."""
    out, k = {}, 0
    for c in companies[:MAX_HIGHLIGHT]:
        if c in FIXED:
            out[c] = FIXED[c]
        else:
            out[c] = EXTRA[k % len(EXTRA)]
            k += 1
    return out


def style(fig, title, ytitle="", height=400, legend=True):
    if ': ' in title:
        main, detail = title.split(': ', 1)
        title_html = f'<b>{main}</b><br><span style="font-size:12px;color:{MUTED}">{detail}</span>'
    elif ' (대칭분해)' in title:
        title_html = f'<b>{title.replace(" (대칭분해)", "")}</b><br><span style="font-size:12px;color:{MUTED}">영업이익 요인 · 금융원가 요인 · 전체 변화</span>'
    else:
        title_html = f'<b>{title}</b>'
    fig.update_layout(
        template='financial_cards',
        title=dict(text=title_html, x=0, xanchor="left", font=dict(size=16, color=INK)),
        height=height, paper_bgcolor="#fff", plot_bgcolor="#fff", font=dict(color=INK, size=12),
        margin=dict(l=20, r=30, t=140 if legend else 95, b=36), showlegend=legend, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        bargap=.42,
    )
    fig.update_xaxes(showgrid=False, showline=False, tickfont=dict(color=MUTED), automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED),
                     title=dict(text=ytitle, font=dict(color=MUTED)), automargin=True)
    return fig


def trend_chart(metrics, field, title, unit, companies, background=(), ref=None, ref_text="",
                ref_color=RED, period=None, clip=None):
    """연도별 추이. companies=강조(최대 5), background=회색 맥락 기업."""
    colors = palette(companies)
    nd = 2 if unit == "배" else 1
    fig, clipped = go.Figure(), []
    data = metrics[metrics.period.isin(X_ORDER)]

    def series(c):
        d = data[data.corp_name == c].set_index("period").reindex(X_ORDER)
        return d

    for c in background:                       # 회색 맥락 (범례·라벨 없음)
        d = series(c)
        fig.add_trace(go.Scatter(x=X_ORDER, y=d[field], mode="lines", line=dict(color=GRAY, width=1),
                                 opacity=.6, showlegend=False, hoverinfo="skip", connectgaps=False))
    for c in [c for c in companies if c in colors]:
        d, col = series(c), colors[c]
        fy = d.loc[FY]
        deficit = ["적자" if (field == "icr" and pd.notna(o) and o < 0) else "" for o in fy["op_income"]]
        fig.add_trace(go.Scatter(
            x=FY, y=fy[field], name=c, mode="lines+markers+text", line=dict(color=col, width=3),
            marker=dict(size=9, color=col, line=dict(color='#fff',width=2)), text=deficit, textposition="bottom center",
            textfont=dict(color=col, size=11), connectgaps=False,
            customdata=[num(v, nd) for v in fy[field]], hovertemplate=f"{c}: %{{customdata}}{unit}<extra></extra>"))
        if pd.notna(d.loc[H1, field]) and pd.notna(d.loc["2025", field]):
            h1_def = "적자" if field == "icr" and pd.notna(d.loc[H1, "op_income"]) and d.loc[H1, "op_income"] < 0 else ""
            fig.add_trace(go.Scatter(
                x=["2025", H1], y=[d.loc["2025", field], d.loc[H1, field]], mode="lines+markers+text",
                showlegend=False, line=dict(color=col, width=2, dash="dot"),
                marker=dict(size=[0, 13], symbol="diamond-open", color=col, line=dict(width=2)),
                text=["", h1_def], textposition="bottom center", textfont=dict(color=col, size=11),
                customdata=["", num(d.loc[H1, field], nd)],
                hovertemplate=f"{c} 2026 상반기: %{{customdata}}{unit}<extra></extra>"))
        if clip:
            for p in X_ORDER:
                v = d.loc[p, field]
                if pd.notna(v) and not (clip[0] <= v <= clip[1]):
                    clipped.append(f"{c} {X_LABEL[p]} {num(v, nd)}{unit}")
    if ref is not None:
        fig.add_hline(y=ref, line=dict(color=ref_color, width=1.6, dash="dash"),
                      annotation_text=ref_text, annotation_position="top left",
                      annotation_font=dict(color=ref_color, size=12))
    i = X_ORDER.index(H1)
    fig.add_vrect(x0=i - .45, x1=i + .45, fillcolor="#FFE066", opacity=.22, line_width=0, layer="below")
    if period in FY:
        j = X_ORDER.index(period)
        fig.add_vrect(x0=j - .45, x1=j + .45, fillcolor="#A5D8FF", opacity=.18, line_width=0, layer="below")
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=X_ORDER,
                     tickvals=X_ORDER, ticktext=[X_LABEL[p] for p in X_ORDER],
                     title=dict(text="사업연도 (2026 상반기는 점선·빈 마름모)", font=dict(color=MUTED)))
    if clip:
        fig.update_yaxes(range=clip)
    style(fig, title, f"{title.split(':')[0].replace(' 추이', '')} ({unit})", height=420)
    if clipped:
        fig.add_annotation(text="축 밖 실제 값<br>" + "<br>".join(clipped[:6]) + (" 외" if len(clipped) > 6 else ""),
                           xref="paper", yref="paper", x=0, y=-.29, yanchor="top", showarrow=False, xanchor="left",align='left',
                           font=dict(size=10, color=MUTED))
        fig.update_layout(height=540,margin=dict(t=140,b=145))
    return fig


def hbar(values: dict, title, unit, ref=None, ref_text="", nd=1, height=None):
    """지표별 가로 막대 (값 순 정렬). values={기업: 값}."""
    items = sorted([(k, v) for k, v in values.items() if pd.notna(v)], key=lambda kv: kv[1])
    names = [k for k, _ in items]
    cols = palette(list(values))
    fig = go.Figure(go.Bar(
        x=[v for _, v in items], y=names, orientation="h",
        marker=dict(color=[cols.get(n, GRAY) for n in names],cornerradius=6),
        text=[num(v, nd) for _, v in items], textposition="outside", cliponaxis=False,
        textfont=dict(color=INK), hovertemplate="%{y}: %{text}" + unit + "<extra></extra>"))
    if ref is not None:
        fig.add_vline(x=ref, line=dict(color=AMBER, width=1.5, dash="dash"),
                      annotation_text=ref_text, annotation_position="top", annotation_font=dict(color=AMBER, size=11))
    style(fig, title, "", height=height or max(300, 130 + 44 * len(names)), legend=False)
    fig.update_layout(hovermode="closest", margin=dict(r=48))
    fig.update_xaxes(showgrid=True, gridcolor=GRID, title=dict(text=unit, font=dict(color=MUTED)))
    return fig


def dumbbell(rows, title, unit="%", nd=1, ref=0):
    """전년 같은 기간 -> 올해 변화. rows=[(기업, 이전값, 현재값)]. 개선=초록, 악화=빨강, 변화 순 정렬."""
    rows = [r for r in rows if pd.notna(r[1]) and pd.notna(r[2])]
    rows.sort(key=lambda r: r[2] - r[1])
    fig = go.Figure()
    for name, a, b in rows:
        col = "#2B8A3E" if b > a else ("#C92A2A" if b < a else MUTED)
        fig.add_trace(go.Scatter(x=[a, b], y=[name, name], mode="lines", line=dict(color=col, width=3),
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[r[1] for r in rows], y=[r[0] for r in rows], mode="markers", name="2025 2분기",
                             marker=dict(size=10, color="#fff", line=dict(color="#868E96", width=2)),
                             customdata=[num(r[1], nd) for r in rows],
                             hovertemplate="%{y} 2025 2분기: %{customdata}" + unit + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=[r[2] for r in rows], y=[r[0] for r in rows], mode="markers+text", name="2026 2분기",
                             marker=dict(size=11, color=INK),
                             text=[f"{num(r[2] - r[1], nd, sign=True)}%p" for r in rows], textposition="middle right",
                             textfont=dict(size=11, color=INK), cliponaxis=False,
                             customdata=[num(r[2], nd) for r in rows],
                             hovertemplate="%{y} 2026 2분기: %{customdata}" + unit + "<extra></extra>"))
    if ref is not None:
        fig.add_vline(x=ref, line=dict(color=MUTED, width=1, dash="dash"))
    style(fig, title, "", height=max(260, 80 + 30 * len(rows)))
    fig.update_layout(hovermode="closest", margin=dict(r=70))
    fig.update_xaxes(showgrid=True, gridcolor=GRID, title=dict(text=f"영업이익률 ({unit})", font=dict(color=MUTED)))
    return fig


def gauge(value, title, kind, threshold=30, caption=""):
    """반원 계기판. kind='icr'(이자보상배율, -5~15배) / 'borrow'(차입금 의존도, 0~60%).
    구간: icr 1배 미만 위험·1~3배 주의·3배 이상 양호 / borrow 참고선-5%p 미만 양호·참고선까지 주의·이상 위험.
    1배·참고선은 앱 기준선, 3배·참고선-5%p는 화면 구분용(공식 기준 아님). 바늘은 범위 밖이면 끝에 고정."""
    if kind == "icr":
        lo, hi, unit, nd = -5, 15, "배", 2
        steps = [(-5, 1, "#D64545", "위험"), (1, 3, "#F2B01E", "주의"), (3, 15, "#2B9A46", "양호")]
    else:
        lo, hi, unit, nd = 0, 60, "%", 1
        steps = [(0, threshold - 5, "#2B9A46", "양호"), (threshold - 5, threshold, "#F2B01E", "주의"),
                 (threshold, 60, "#D64545", "위험")]
    ok = value is not None and pd.notna(value)
    needle = min(max(float(value), lo), hi) if ok else None
    fig = go.Figure(go.Indicator(
        mode="gauge", value=needle if ok else lo,
        gauge=dict(axis=dict(range=[lo, hi], tickwidth=0, tickcolor="#9aa5b1", tickfont=dict(size=10, color=MUTED),nticks=4),
                   bar=dict(color="rgba(0,0,0,0)", thickness=0),
                   steps=[dict(range=[a, b], color=c,thickness=.24) for a, b, c, _ in steps],
                   threshold=dict(line=dict(color=INK, width=4), thickness=.42, value=needle if ok else lo),
                   borderwidth=0, bgcolor="#fff"),
        domain=dict(x=[0.08, .92], y=[0.27, .78])))
    zone = next((n for a, b, c, n in steps if ok and a <= needle <= b), "자료 없음")
    out = "" if not ok or lo <= value <= hi else (" ▶" if value > hi else " ◀")
    fig.add_annotation(x=0.5, y=0.32, xref="paper", yref="paper", showarrow=False,
                       text=(f"<b>{num(value, nd)}{unit}</b>{out}" if ok else "<b>자료 없음</b>"),
                       font=dict(size=30, color=INK))
    fig.add_annotation(x=0.5, y=0.02, xref="paper", yref="paper", showarrow=False,
                       text=f"{zone} · {caption}" if caption else zone, font=dict(size=12, color=MUTED),bgcolor='#F5F5F7',borderpad=6)
    heading = title.replace(' · ', '</b><br><span style="font-size:11px;color:#7B7C86">')
    heading = f'<b>{heading}</span>' if ' · ' in title else f'<b>{title}</b>'
    fig.update_layout(title=dict(text=heading, x=0.5, xanchor="center", font=dict(size=13, color=INK)),
                      height=270, margin=dict(l=12, r=12, t=54, b=24), paper_bgcolor="#fff")
    return fig
