"""RM 인사이트 탭: 선택 기업의 숫자로 인사이트 3개와 RM 상담 방향 4개를 자동으로 만든다.

- 수치는 metrics.csv·quarterly_metrics.csv 값만 사용 (표시용 차이·시나리오 계산만 수행)
- 대출 가부를 단정하지 않고 '점검 항목'으로 표현. 참고용이며 실제 은행 심사 기준이 아님
"""
from html import escape

import pandas as pd
import streamlit as st

from chart_style import num
from credit_logic import RESPONSES, STAGE_COLORS, headroom, loss_streak, valid
from credit_ui import management

Y = "#F5B700"  # 강조(노랑)

CSS = f"""
<style>
.ins-label{{color:#9a7400;font-weight:800;font-size:13px;letter-spacing:.08em}}
.ins-bar{{height:5px;width:64px;background:{Y};border-radius:3px;margin:6px 0 10px}}
.ins-title{{font-size:1.65rem;font-weight:800;color:#1f2d3d;line-height:1.3;margin:2px 0 4px}}
.ins-sub{{color:#9a7400;font-size:1.05rem;font-weight:700;margin-bottom:14px}}
.ins-row{{display:flex;gap:14px;align-items:flex-start;background:#fff;border:1px solid #e3e8ee;border-radius:14px;padding:14px 16px;margin-bottom:10px}}
.ins-n{{flex:0 0 34px;height:34px;border-radius:50%;background:{Y};color:#1f2d3d;font-weight:900;display:flex;align-items:center;justify-content:center}}
.ins-row b{{color:#1f2d3d}} .ins-row .t{{color:#38546b;font-size:15px;line-height:1.6}}
.rm-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:6px}}
@media (max-width:900px){{.rm-grid{{grid-template-columns:1fr}}}}
.rm{{background:#fff;border:1px solid #e3e8ee;border-radius:16px;padding:16px 18px;position:relative}}
.rm h4{{margin:0 0 4px;font-size:1.05rem;color:#1f2d3d}}
.rm .ic{{position:absolute;top:14px;right:14px;width:34px;height:34px;border-radius:50%;background:{Y};display:flex;align-items:center;justify-content:center;font-size:16px}}
.rm .cap{{color:#2a78d6;font-size:12.5px;font-weight:700;margin-bottom:8px}}
.rm .q{{color:#38546b;font-size:14.5px;line-height:1.65}}
.rm .hl{{background:#FFE58F;padding:1px 4px;border-radius:3px;font-weight:700;color:#1f2d3d}}
.rm .bar{{display:flex;justify-content:space-between;background:#eef1f5;border-radius:6px;padding:6px 10px;margin:5px 0;font-size:13.5px;color:#38546b}}
.rm .bar b{{color:#1f2d3d}} .rm .bar.key{{background:#FFF4CC}}
.rm .ck{{font-size:14px;color:#38546b;line-height:1.6;margin:2px 0}}
.peer-t{{width:100%;border-collapse:collapse;font-size:13.5px;background:#fff;border-radius:12px;overflow:hidden}}
.peer-t th{{background:#f3f5f8;color:#6b7a8c;text-align:left;padding:8px 10px;font-weight:700}}
.peer-t td{{padding:8px 10px;border-top:1px solid #eef1f5;color:#38546b}}
.limit{{background:#2b3240;color:#e8ecf2;border-radius:14px;padding:14px 18px;font-size:13.5px;line-height:1.7;margin-top:14px}}
.limit b{{color:#FFD43B}}
</style>
"""


def _row(df, corp, period):
    d = df[(df.corp_name == corp) & (df.period == period)]
    return None if d.empty else d.iloc[0]


def _prior(metrics, period, corp=None):
    """전년 같은 기간: 연간은 전년, 반기는 전년 반기(그 기업에 없으면 전년 연간)."""
    if period.isdigit():
        return str(int(period) - 1)
    same = f"{int(period[:4]) - 1}H1"
    pool = metrics if corp is None else metrics[metrics.corp_name == corp]
    return same if same in set(pool.period) else str(int(period[:4]) - 1)


def _pct(v):
    return f"{num(v)}%" if valid(v) else "자료 없음"


def _icr(r):
    if r is None or not valid(r.icr):
        return "자료 없음"
    s = f"{num(r.icr, 2)}배"
    if valid(r.op_income) and r.op_income < 0:
        s += "(적자)"
    return s


def render_insight(metrics, quarterly, quality, companies, target, period, threshold):
    st.markdown(CSS, unsafe_allow_html=True)
    r = _row(metrics, target, period)
    if r is None:
        st.info(f"{target}의 {period} 재무 데이터가 없어 인사이트를 만들 수 없습니다. 다른 기간을 선택하세요.")
        return
    prev = _prior(metrics, period, target)
    p = _row(metrics, target, prev)
    stg = management(r, quality, threshold)
    streak = loss_streak(metrics.to_dict("records"), target, period)
    peers = [c for c in companies if c != target]
    cur = metrics[(metrics.corp_name.isin(companies)) & (metrics.period == period)]

    # ---------- 결론형 제목 ----------
    if valid(r.icr) and r.icr < 1:
        head = f"{target}, 이익으로 이자를 못 넘는 구간: 이익 위험과 차입 위험을 따로 점검한다"
    elif valid(r.borrow_dep) and r.borrow_dep >= threshold:
        head = f"{target}, 이익은 이자를 넘지만 빚 비중이 높다: 차입 구조를 먼저 본다"
    elif stg == "판정 보류":
        head = f"{target}, 숫자가 비어 있다: 판단 전에 누락 계정부터 확인한다"
    else:
        head = f"{target}, 재무 기준선 안쪽: 비재무 위험(원료 조달) 중심으로 본다"
    st.markdown(f"<div class='ins-label'>RM 인사이트 · {escape(period)}</div><div class='ins-bar'></div>"
                f"<div class='ins-title'>{escape(head)}</div>"
                f"<div class='ins-sub'>이 결과를 은행 상담에 어떻게 쓰나 · 관리 단계 "
                f"<span style='color:{STAGE_COLORS.get(stg, '#657586')}'>{escape(stg)}</span></div>",
                unsafe_allow_html=True)

    # ---------- 인사이트 3(+1)개 ----------
    def delta(field, unit="%p", nd=1):
        if p is None or not valid(r[field]) or not valid(p[field]):
            return ""
        return f" ({escape(prev)} 대비 {num(r[field] - p[field], nd, sign=True)}{unit})"

    def rank(field, high_good=True):
        s = cur[["corp_name", field]].dropna()
        if len(s) < 2 or target not in set(s.corp_name):
            return ""
        s = s.sort_values(field, ascending=not high_good).reset_index(drop=True)
        k = int(s.index[s.corp_name == target][0]) + 1
        med = s[field].median()
        return f", 선택 {len(s)}곳 중 {k}위(중앙값 {num(med)})"

    items = [
        f"<b>돈을 벌고 있나</b> · 영업이익률 <b>{_pct(r.op_margin)}</b>{delta('op_margin')}{rank('op_margin')}.",
    ]
    t2 = f"<b>이자를 감당하나</b> · 이자보상배율 <b>{_icr(r)}</b>{delta('icr', '배', 2)}"
    if streak >= 3:
        t2 += f", 연간 <b>{streak}년 연속 1배 미만</b>(한계기업 참고조건, 공식 분류 아님)"
    elif streak > 0:
        t2 += f", 연간 {streak}년 연속 1배 미만"
    items.append(t2 + ".")
    items.append(f"<b>빚이 늘고 있나</b> · 부채비율 <b>{_pct(r.debt_ratio)}</b>{delta('debt_ratio')}, "
                 f"차입금 의존도 <b>{_pct(r.borrow_dep)}</b>{delta('borrow_dep')}"
                 f" · 참고선 {threshold}% {'이상' if valid(r.borrow_dep) and r.borrow_dep >= threshold else '미만'}.")
    q25 = _row(quarterly, target, "2025Q2") if not quarterly.empty else None
    q26 = _row(quarterly, target, "2026Q2") if not quarterly.empty else None
    if q25 is not None and q26 is not None and valid(q25.op_margin) and valid(q26.op_margin):
        items.append(f"<b>충격 분기(2026 2분기)</b> · 영업이익률 {num(q25.op_margin)}% → <b>{num(q26.op_margin)}%</b> "
                     f"({num(q26.op_margin - q25.op_margin, 1, sign=True)}%p). 재고평가·환율 등 일회성 가능성을 함께 본다.")
    st.markdown("".join(f"<div class='ins-row'><div class='ins-n'>{i}</div><div class='t'>{t}</div></div>"
                        for i, t in enumerate(items, 1)), unsafe_allow_html=True)

    # ---------- RM 상담 방향 4개 ----------
    # ① 원인별 설명 (상담 문장 예시)
    om = f"영업이익률 {_pct(r.op_margin)}" + (f"로 {prev} 대비 {num(r.op_margin - p.op_margin, 1, sign=True)}%p" if p is not None and valid(p.op_margin) and valid(r.op_margin) else "")
    if valid(r.icr) and r.icr < 1:
        why = f"하지만 이자보상배율은 {num(r.icr, 2)}배라 영업이익이 아직 금융비용을 넘지 못합니다."
    elif valid(r.icr):
        why = f"이자보상배율은 {num(r.icr, 2)}배로 영업이익이 금융비용을 넘고 있습니다."
    else:
        why = "이자보상배율은 자료가 없어 판단을 보류합니다."
    card1 = (f"<div class='rm'><div class='ic'>💬</div><h4>① 지금 상태를 원인별로 설명</h4>"
             f"<div class='cap'>상담 예시 · {escape(period)}</div>"
             f"<div class='q'>\"{escape(target)}의 {escape(period)} {om}입니다. {why}\"</div></div>")

    # ② 두 위험을 따로
    profit = ("이익 위험 <span class='hl'>높음</span>: 1배 미만" + (f" {streak}년 연속" if streak else "")) if valid(r.icr) and r.icr < 1 \
        else ("이익 위험 낮음: 1배 이상" if valid(r.icr) else "이익 위험 판단 보류")
    debt = (f"차입 위험 <span class='hl'>높음</span>: 의존도 {num(r.borrow_dep)}% ≥ {threshold}%" if valid(r.borrow_dep) and r.borrow_dep >= threshold
            else (f"차입 위험 낮음: 의존도 {num(r.borrow_dep)}%" if valid(r.borrow_dep) else "차입 위험 판단 보류(차입금 매핑 확인)"))
    card2 = (f"<div class='rm'><div class='ic'>⚠️</div><h4>② 두 위험을 따로 점검</h4>"
             f"<div class='cap'>이익으로 이자를 내는 힘 vs 빌린 돈의 무게</div>"
             f"<div class='q'>{profit}<br>{debt}<br>→ 한 지표가 좋아도 다른 위험을 대신 판단하지 않습니다.</div></div>")

    # ③ 앞으로 확인할 신호 (시나리오 값)
    bars = []
    h = headroom(r.icr)
    if h is not None:
        bars.append(("영업이익이 이만큼 줄면 1배 도달", f"-{num(h)}%", True))
    elif valid(r.icr) and valid(r.interest_expense) and valid(r.op_income) and r.interest_expense > 0:
        gap = (r.interest_expense - r.op_income) / 1e8
        bars.append(("1배 회복에 필요한 영업이익 개선", f"+{num(gap, 0)}억원", True))
    if valid(r.borrow_dep):
        room = threshold - r.borrow_dep
        bars.append(("차입금 의존도 참고선까지", f"{num(room, 1, sign=True)}%p", room < 0))
    if q25 is not None and q26 is not None and valid(q25.op_margin) and valid(q26.op_margin):
        bars.append(("충격 분기 영업이익률 변화", f"{num(q26.op_margin - q25.op_margin, 1, sign=True)}%p", False))
    card3 = (f"<div class='rm'><div class='ic'>📈</div><h4>③ 앞으로 확인할 신호</h4>"
             f"<div class='cap'>시나리오 값 · metrics.csv 값으로 계산 (원본 아님)</div>"
             + "".join(f"<div class='bar{' key' if k else ''}'><span>{escape(a)}</span><b>{escape(b)}</b></div>" for a, b, k in bars)
             + "</div>")

    # ④ 점검 항목
    checks = [f"<b>관리 단계 {escape(stg)}</b>: {escape(RESPONSES.get(stg, ''))}"]
    if valid(r.icr) and r.icr < 1:
        checks.append("<b>이익이 부족할 때</b>: 만기연장·금리 조건, 다음 분기 이익의 일회성 여부")
    if valid(r.borrow_dep) and r.borrow_dep >= threshold:
        checks.append("<b>빚 비중이 클 때</b>: 단기차입 비중, 차환 계획, 만기 구조")
    if str(r.get("icr_basis", "")) == "금융원가":
        checks.append("<b>분모 확인</b>: 금융원가 기준(외환손실 포함) → 주석의 실제 이자비용 대조")
    if "H1" in period:
        checks.append("<b>비재무</b>: 원료(나프타) 조달 경로·재고 일수")
    card4 = (f"<div class='rm'><div class='ic'>📋</div><h4>④ 상황에 맞는 점검 항목</h4>"
             f"<div class='cap'>상품 권유가 아닌 상담 시 점검 항목</div>"
             + "".join(f"<div class='ck'>{c}</div>" for c in checks) + "</div>")
    st.markdown("<div class='ins-label' style='margin-top:18px'>RM 상담 방향</div><div class='ins-bar'></div>"
                f"<div class='rm-grid'>{card1}{card2}{card3}{card4}</div>", unsafe_allow_html=True)

    # ---------- 비교 기업 한 줄 ----------
    if peers:
        rows = []
        for c in companies:
            x = _row(metrics, c, period)
            if x is None:
                rows.append(f"<tr><td>{escape(c)}</td><td colspan='5'>{escape(period)} 자료 없음 · 판정 보류</td></tr>")
                continue
            s = management(x, quality, threshold)
            rows.append(f"<tr><td><b>{escape(c)}</b>{' (대상)' if c == target else ''}</td>"
                        f"<td style='color:{STAGE_COLORS.get(s, '#657586')};font-weight:700'>{escape(s)}</td>"
                        f"<td>{_pct(x.op_margin)}</td><td>{_icr(x)}</td><td>{_pct(x.borrow_dep)}</td>"
                        f"<td>{escape(RESPONSES.get(s, ''))}</td></tr>")
        st.markdown("<div class='ins-label' style='margin-top:18px'>비교 기업 한눈에</div><div class='ins-bar'></div>"
                    "<table class='peer-t'><tr><th>기업</th><th>관리 단계(참고)</th><th>영업이익률</th><th>이자보상배율†</th>"
                    "<th>차입금 의존도</th><th>점검 방향</th></tr>" + "".join(rows) + "</table>", unsafe_allow_html=True)

    render_icr_decomposition(metrics, target)

    st.markdown("<div class='limit'><b>해석의 한계</b><br>관리 단계와 기준선(1배·참고선)은 참고용이며 실제 은행 심사 기준·대출 가부가 아닙니다 · "
                "† 이자보상배율은 이자비용이 없으면 금융원가 기준 · 반기·분기는 검토 재무제표이며 일회성·계절성 영향이 큼 · "
                "연결재무제표로는 사업부별 효과를 나눌 수 없음 · 투자 권유 아님</div>", unsafe_allow_html=True)


def icr_decomposition(metrics, corp):
    """연간 이자보상배율 변화 = 영업이익 요인 + 금융원가(이자) 요인 (대칭분해, 교차항을 절반씩).
    ICR = OP / INT 일 때
      이익 요인 = ((OP1 - OP0)/INT0 + (OP1 - OP0)/INT1) / 2
      이자 요인 = ((OP0/INT1 - OP0/INT0) + (OP1/INT1 - OP1/INT0)) / 2
      두 요인의 합 = ICR1 - ICR0 (정확히 일치)"""
    d = metrics[(metrics.corp_name == corp) & (metrics.period.astype(str).str.fullmatch(r"\d{4}"))].copy()
    d = d.sort_values("period")
    rows = []
    for (_, a), (_, b) in zip(d.iterrows(), d.iloc[1:].iterrows()):
        op0, op1, i0, i1 = a.op_income, b.op_income, a.interest_expense, b.interest_expense
        if not all(valid(v) for v in (op0, op1, i0, i1)) or i0 <= 0 or i1 <= 0:
            continue
        profit = ((op1 - op0) / i0 + (op1 - op0) / i1) / 2
        interest = ((op0 / i1 - op0 / i0) + (op1 / i1 - op1 / i0)) / 2
        rows.append({"period": str(b.period), "prev": str(a.period), "icr0": op0 / i0, "icr1": op1 / i1,
                     "d_icr": op1 / i1 - op0 / i0, "profit": profit, "interest": interest,
                     "op0": op0, "op1": op1, "i0": i0, "i1": i1})
    return pd.DataFrame(rows)


def render_icr_decomposition(metrics, corp):
    import plotly.graph_objects as go
    from chart_style import style
    dec = icr_decomposition(metrics, corp)
    st.markdown("<div class='ins-label' style='margin-top:18px'>이자보상배율은 왜 변했나 · 원인 분해</div><div class='ins-bar'></div>",
                unsafe_allow_html=True)
    if dec.empty:
        st.info(f"{corp}는 연속된 연간 영업이익·금융원가 자료가 없어 분해할 수 없습니다.")
        return
    fig = go.Figure()
    hov = "%{x}<br>%{fullData.name} %{y:+.2f}배<extra></extra>"
    fig.add_trace(go.Bar(x=dec.period, y=dec.profit, name="영업이익 요인", marker=dict(color="#E9B949",cornerradius=5), hovertemplate=hov))
    fig.add_trace(go.Bar(x=dec.period, y=dec.interest, name="금융원가(이자) 요인", marker=dict(color="#8895BA",cornerradius=5), hovertemplate=hov))
    fig.add_trace(go.Scatter(x=dec.period, y=dec.d_icr, name="이자보상배율 변화", mode="lines+markers+text",
                             line=dict(color="#1f2d3d", width=2), marker=dict(size=8),
                             text=[num(v, 2, sign=True) for v in dec.d_icr], textposition="top center",
                             textfont=dict(color="#1f2d3d", size=11), hovertemplate=hov))
    fig.add_hline(y=0, line=dict(color="#9aa5b1", width=1))
    style(fig, f"{corp} 연간 이자보상배율 변화와 원인 (대칭분해)", "배 (전년 대비 변화)", height=400)
    fig.update_layout(barmode="relative", hovermode="x unified")
    fig.update_xaxes(type="category")
    st.plotly_chart(fig, width="stretch")
    st.caption("영업이익 요인 + 금융원가 요인 = 그해 이자보상배율 변화 (교차항을 절반씩 나눈 대칭분해) · "
               "금융원가가 늘면 이자 요인은 음수 · † 금융원가 기준 · 분해 값은 metrics.csv 금액으로 계산(원본 아님)")

    top = dec.assign(abs_change=dec.d_icr.abs()).nlargest(min(5, len(dec)), "abs_change")
    show = pd.DataFrame({
        "연도": top.prev + " → " + top.period,
        "이자보상배율": [f"{num(a, 2)} → {num(b, 2)}배" for a, b in zip(top.icr0, top.icr1)],
        "변화": [f"{num(v, 2, sign=True)}배" for v in top.d_icr],
        "영업이익 요인": [f"{num(v, 2, sign=True)}배" for v in top.profit],
        "금융원가 요인": [f"{num(v, 2, sign=True)}배" for v in top.interest],
        "더 큰 쪽": ["영업이익" if abs(a) >= abs(b) else "금융원가" for a, b in zip(top.profit, top.interest)],
    })
    st.markdown("**변화가 컸던 해**")
    st.dataframe(show, hide_index=True, width="stretch")

    pick = st.selectbox("상담할 연도 고르기", dec.period.tolist()[::-1], key=f"dec_pick_{corp}")
    r = dec.set_index("period").loc[pick]
    big = "영업이익" if abs(r.profit) >= abs(r.interest) else "금융원가(이자)"
    op_chg = (r.op1 - r.op0) / 1e8
    int_chg = (r.i1 - r.i0) / 1e8
    st.info(f"**{r.prev} → {pick}** {corp}의 이자보상배율이 {num(r.icr0, 2)}배에서 {num(r.icr1, 2)}배로 "
            f"{num(r.d_icr, 2, sign=True)}배 변했습니다. 영업이익이 {num(op_chg, 0, sign=True)}억원 변한 영향이 "
            f"{num(r.profit, 2, sign=True)}배, 금융원가가 {num(int_chg, 0, sign=True)}억원 변한 영향이 {num(r.interest, 2, sign=True)}배로 "
            f"이번에는 **{big}** 쪽 영향이 더 컸습니다. "
            + ("→ 상담에서는 이익 회복 계획(가동률·스프레드)을 먼저 확인합니다." if big == "영업이익"
               else "→ 상담에서는 차입 규모·금리 조건과 금융원가 구성(외환손실 포함 여부)을 먼저 확인합니다."))
    if r.op0 < 0 or r.op1 < 0:
        st.warning("영업적자 구간에서는 금융원가가 늘수록 배율이 0에 가까워져 '개선'처럼 보입니다. "
                   "적자 연도는 금융원가 요인보다 영업이익 요인(적자 폭 변화)을 중심으로 해석하세요.")


def render_gauges(metrics, companies, period, threshold):
    """여신 계기판: 선택 기업(최대 5곳)의 이자보상배율·차입금 의존도 바늘 위치."""
    from chart_style import gauge, MAX_HIGHLIGHT
    show = companies[:MAX_HIGHLIGHT]
    st.markdown(f"<div class='ins-label'>여신 계기판 · {escape(period)}</div><div class='ins-bar'></div>", unsafe_allow_html=True)
    for kind, label in (("icr", "이자보상배율†"), ("borrow", "차입금 의존도")):
        cols = st.columns(len(show))
        for col, c in zip(cols, show):
            r = _row(metrics, c, period)
            v = None if r is None else (r.icr if kind == "icr" else r.borrow_dep)
            cap = ""
            if kind == "icr" and r is not None and valid(r.op_income) and r.op_income < 0:
                cap = "영업적자"
            with col:
                st.plotly_chart(gauge(v, f"{c} · {label}", kind, threshold, cap), width="stretch",
                                key=f"gauge_{kind}_{c}", config={"displayModeBar": False})
    st.caption(f"바늘 = {period} 값 · 이자보상배율 1배, 차입금 의존도 {threshold}%는 앱 기준선(참고용), "
               f"3배·{threshold - 5}%는 화면 구분용 구간이며 실제 은행 심사 기준이 아님 · 범위 밖 값은 ▶◀ 표시")
