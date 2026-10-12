"""여신 계기판 한눈에 보기 (PPT 30·32·33장, 보고서 10-2).

은행 판단 탭 맨 위에 붙이는 요약 화면 3개:
  ① 3초 요약: 경고등 4개 + 관리 단계 + 플래그
  ② 관리 단계 이동: 기업 × 연도 표
  ③ 버틸 여력: 헤드룸과 "2022년 같은 충격" 비교
숫자는 metrics.csv에서만 가져오고, 판정·계산은 credit_logic.py 함수를 그대로 쓴다.
관리 단계와 기준선은 참고용이며 실제 은행 심사 기준이 아니다. 투자 권유 아님.
"""
import pandas as pd
import streamlit as st

from credit_logic import RESPONSES, headroom, stress, valid
from credit_ui import PERIODS, flags, management, number

ON, OFF = '●', '○'


def _row(metrics, corp, period):
    hit = metrics[(metrics.corp_name == corp) & (metrics.period == period)]
    return None if hit.empty else hit.iloc[0]


def _annual_runs(metrics, corp, last_year):
    """연간 이자보상배율 1배 미만 연속 구간 목록 [(시작, 끝), ...]. H1은 세지 않는다."""
    annual = metrics[(metrics.corp_name == corp) & metrics.period.astype(str).str.fullmatch(r'\d{4}')]
    years = sorted(int(p) for p in annual.period if int(p) <= last_year)
    icr = {int(p): v for p, v in zip(annual.period, annual.icr)}
    runs, start = [], None
    for y in years:
        bad = valid(icr[y]) and icr[y] < 1
        if bad and start is None:
            start = y
        if not bad and start is not None:
            runs.append((start, y - 1)); start = None
    if start is not None:
        runs.append((start, years[-1]))
    return runs


def zombie_light(metrics, corp, period):
    """한계기업 참고조건(연간 3년 연속 1배 미만). 2026H1이면 2025년까지로 판정."""
    last = int(str(period)[:4]) - (1 if 'H' in str(period) else 0)
    runs = [r for r in _annual_runs(metrics, corp, last) if r[1] - r[0] + 1 >= 3]
    if runs and runs[-1][1] == last:
        s, e = runs[-1]
        return ON, f'{e - s + 1}년 ({s}~{e})'
    if runs:
        s, e = runs[-1]
        return OFF, f'해제 ({s}~{e})'
    return OFF, '해당 없음'


def summary_table(metrics, quarterly, events, quality, companies, period, threshold):
    rows = []
    for corp in companies:
        r = _row(metrics, corp, period)
        if r is None:
            continue
        z_on, z_text = zombie_light(metrics, corp, period)
        tags = flags(r, metrics, quarterly, events)
        rows.append({
            '기업': corp,
            '영업적자': (ON + ' 적자 ' if valid(r.op_income) and r.op_income < 0 else OFF + ' 흑자 ') + number(r.op_margin),
            '이자보상배율† 1배 미만': (ON if valid(r.icr) and r.icr < 1 else OFF) + ' ' + number(r.icr, '배'),
            '한계기업 (3년 연속)': z_on + ' ' + z_text,
            f'차입금 의존도 {threshold}% 이상': (ON if valid(r.borrow_dep) and r.borrow_dep >= threshold else OFF) + ' ' + number(r.borrow_dep),
            '관리 단계': management(r, quality, threshold),
            '플래그': ' · '.join(tags) or '없음',
        })
    return pd.DataFrame(rows)


def stage_timeline(metrics, quality, companies, period, threshold):
    cols = [p for p in PERIODS if p <= period or (period.endswith('H1') and p[:4] <= period[:4])]
    table = {'기업': []}
    for p in cols:
        table['2026 상반기' if p == '2026H1' else p] = []
    for corp in companies:
        table['기업'].append(corp)
        for p in cols:
            r = _row(metrics, corp, p)
            key = '2026 상반기' if p == '2026H1' else p
            if r is None:
                table[key].append('자료 없음'); continue
            icr = '적자' if valid(r.op_income) and r.op_income < 0 else number(r.icr, '배')
            table[key].append(f"{management(r, quality, threshold).split(' (')[0]} ({icr} · {number(r.borrow_dep)})")
    return pd.DataFrame(table)


def shock_table(metrics, quality, companies, period, threshold):
    rows = []
    for corp in companies:
        r = _row(metrics, corp, period)
        y21, y22 = _row(metrics, corp, '2021'), _row(metrics, corp, '2022')
        if r is None:
            continue
        hist = None
        if y21 is not None and y22 is not None and valid(y21.op_income) and y21.op_income > 0 and valid(y22.op_income):
            hist = y22.op_income / y21.op_income - 1
        new = stress(r.icr, r.op_income, historical_change=hist) if hist is not None else None
        after = r.copy()
        if new is not None:
            after['icr'] = new
        h = headroom(r.icr)
        rows.append({
            '기업': corp,
            '지금 이자보상배율†': number(r.icr, '배'),
            '헤드룸': number(h) if h is not None else ('기준선 아래' if valid(r.icr) else '자료 없음'),
            '2021→2022 영업이익 변화': number(hist * 100) if hist is not None else '계산 불가',
            '충격 후 이자보상배율 (시나리오)': number(new, '배') if new is not None else '계산 불가',
            '관리 단계': management(r, quality, threshold) + ' → ' + (management(after, quality, threshold) if new is not None else '-'),
        })
    return pd.DataFrame(rows)


def render_dashboard(metrics, quarterly, events, quality, companies, period, threshold):
    st.subheader('여신 계기판 · 3초 요약')
    st.caption('● 경고등 켜짐 ○ 꺼짐 · † 이자보상배율은 금융원가 기준(3사 모두 이자비용 계정 없음) · '
               '한계기업은 연간 값만으로 3년 연속 1배 미만을 판정(상반기는 세지 않음)')
    summary = summary_table(metrics, quarterly, events, quality, companies, period, threshold)
    if summary.empty:
        st.info('선택한 기간에 표시할 기업 자료가 없습니다.')
        return
    st.dataframe(summary, hide_index=True, width='stretch')
    for _, s in summary.iterrows():
        st.caption(f"{s['기업']} · {s['관리 단계']} → {RESPONSES.get(s['관리 단계'], '')}")

    st.subheader('관리 단계 이동 · 어디서 왔나')
    st.dataframe(stage_timeline(metrics, quality, companies, period, threshold), hide_index=True, width='stretch')
    st.caption('괄호: 이자보상배율†(영업적자면 "적자") · 차입금 의존도. 2026 상반기는 상반기 누적 이자보상배율, 6월 말 차입금 의존도.')

    st.subheader('버틸 여력 · 2022년 같은 충격이 다시 오면')
    st.dataframe(shock_table(metrics, quality, companies, period, threshold), hide_index=True, width='stretch')
    st.caption('헤드룸 = 이자보상배율이 1배가 될 때까지 영업이익이 더 줄 수 있는 비율. '
               '충격 후 = 지금 영업이익 × (1 + 2021→2022 영업이익 변화율) ÷ 같은 이자비용. '
               '차입금 의존도는 고정. 시나리오 값이며 원본이 아님.')
    st.caption('관리 단계와 기준선은 참고용이며 실제 은행 심사 기준이 아닙니다 · 투자 권유 아님')
    st.divider()
