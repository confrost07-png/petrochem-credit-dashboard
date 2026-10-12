"""통합 설계 v2의 관리지도·시나리오·심사 메모 화면."""
from html import escape
from collection_status import missing_message
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from review_ui import render_review
from credit_logic import RESPONSES, STAGE_COLORS, stage, headroom, stress, loss_streak, clip_icr, valid

PERIODS=['2021','2022','2023','2024','2025','2026H1']
SOURCE_RISK='https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/171980/view'

def number(v,unit='%',digits=2):
    return f'{v:,.{digits}f}{unit}' if valid(v) else '자료 없음'

def readiness(row,quality):
    if quality.empty:return True
    hit=quality[(quality.corp_name==row.corp_name)&(quality.period==row.period)]
    return len(hit)==1 and str(hit.iloc[0].management_ready)=='Y'

def management(row,quality,threshold=30):
    if row is None:return '판정 보류'
    return stage(row.icr,row.borrow_dep,row.equity,threshold,readiness(row,quality))

def flags(row,metrics,quarterly,events):
    result=[]
    period=str(row.period);end=period[:4]+('-06-30' if 'H' in period else '-12-31')
    start=period[:4]+'-01-01'
    if not events.empty:
        ev=events[(events.corp_name==row.corp_name)&(events.date>=start)&(events.date<=end)]
        if ev.type.str.contains('영구채',na=False).any(): result.append('영구채·자본분류 확인')
        # 편입·연결 범위 변경은 전년 동기 비교에 영향 → 비교 기간(전년 1월 1일)부터 확인
        wide=events[(events.corp_name==row.corp_name)&(events.date>=str(int(period[:4])-1)+'-01-01')&(events.date<=end)]
        for _,e in wide[wide.type.astype(str).eq('편입')].iterrows():
            name=str(e.event).split('연결 편입')[0].replace('(주)','').strip() or '편입'
            result.append(f'연결 범위 변경({name})')
    if period=='2026H1':result.append('원료 조달·업종 공통 점검')
    prior=quarterly if 'H' in period else metrics
    prior_period=str(int(period[:4])-1)+('H1' if 'H' in period else '')
    p=prior[(prior.corp_name==row.corp_name)&(prior.period==prior_period)]
    if not p.empty and valid(p.iloc[0].op_income) and valid(row.op_income) and p.iloc[0].op_income<0<row.op_income:
        result.append('흑자 전환·동일 기간 비교')
    return result

import chart_style as cs

LO,HI=-5,15   # 지도 가로축 표시 범위 (밖은 가장자리 화살표 + 실제 값)
SHORT={'2021':"'21",'2022':"'22",'2023':"'23",'2024':"'24",'2025':"'25",'2026H1':"'26 상반기"}
ZONES=[  # (x0,x1, 아래/위, 단계, 배경, 설명)
    (LO,1,'low','관리 강화 (이익 부족)','#FFF8EF','이익으로 이자 못 냄 · 빚 비중은 낮음'),
    (1,HI,'low','정상 관리','#EFF8F5','이자 감당 · 빚 비중 낮음'),
    (LO,1,'high','집중 관리','#FFF0F0','이자 못 냄 + 빚 비중 높음'),
    (1,HI,'high','관찰 (빚 부담)','#FFFAEA','이자 감당 · 빚 비중 높음'),
]

def _xy(row,value=None):
    v=row.icr if value is None else value
    x,arrow=clip_icr(v,LO,HI)
    return x,(row.borrow_dep if valid(row.borrow_dep) else None),arrow,v

def _base(fig,threshold,top):
    for x0,x1,band,name,fill,desc in ZONES:
        y0,y1=(0,threshold) if band=='low' else (threshold,top)
        fig.add_shape(type='rect',x0=x0,x1=x1,y0=y0,y1=y1,fillcolor=fill,line_width=0,layer='below')
        left=x0==LO
        fig.add_annotation(x=x0+.15 if left else x1-.15,y=y1-top*.015,
            xanchor='left' if left else 'right',yanchor='top',showarrow=False,align='left' if left else 'right',
            text=f'<b>{name}</b><br><span style="font-size:11px">{desc}</span>',
            font=dict(size=13,color=STAGE_COLORS[name]),bgcolor='rgba(255,255,255,.6)',borderpad=3)
    fig.add_shape(type='line',x0=1,x1=1,y0=0,y1=top,line=dict(color='#495057',width=1.6,dash='dash'))
    fig.add_shape(type='line',x0=LO,x1=HI,y0=threshold,y1=threshold,line=dict(color='#495057',width=1.6,dash='dash'))
    fig.add_annotation(x=1,y=top*.985,yanchor='top',xanchor='left',xshift=4,showarrow=False,bgcolor='rgba(255,255,255,.85)',
        text='<b>1배</b> 참고선',font=dict(size=11,color='#495057'))
    fig.add_annotation(x=HI,y=threshold,xanchor='left',yanchor='middle',showarrow=False,
        text=f'<b>{threshold:g}%</b><br>참고선',font=dict(size=11,color='#495057'))

def _layout(fig,title,top,height=560,legend=True):
    fig.update_layout(title=dict(text=title,x=0,xanchor='left',font=dict(size=16,color=cs.INK)),
        height=height,margin=dict(l=70,r=70,t=80,b=110),paper_bgcolor='#fff',plot_bgcolor='#fff',
        font=dict(color='#38546b',size=12),showlegend=legend,hovermode='closest',
        legend=dict(orientation='h',yanchor='top',y=-.17,xanchor='left',x=0,title=None,font=dict(size=12)),
        xaxis=dict(range=[LO-.4,HI+.4],fixedrange=True,zeroline=False,showgrid=False,
            tickvals=[-5,0,1,3,5,10,15],ticktext=['-5 이하','0','1','3','5','10','15 이상'],
            title=dict(text='← 이자를 못 냄 · 이자보상배율† (배) · 이자를 감당함 →',font=dict(size=13))),
        yaxis=dict(range=[0,top],fixedrange=True,gridcolor=cs.GRID,zeroline=False,ticksuffix='%',
            title=dict(text='차입금 의존도 (%) · 위로 갈수록 빚 비중 큼',font=dict(size=13))))

def credit_map(metrics,companies,period,threshold,target,trail='심사 대상만'):
    """여신 관리 지도: 강조 기업(최대 5)만 색·이름, 나머지는 회색 점. 궤적은 선택형."""
    order=[target]+[c for c in companies if c!=target] if target in companies else list(companies)
    colors=cs.palette(order)
    cur=metrics[metrics.corp_name.isin(companies)&(metrics.period==period)].set_index('corp_name')
    hist=metrics[metrics.corp_name.isin(colors)&metrics.period.isin(PERIODS)]
    ys=pd.to_numeric(pd.concat([cur.borrow_dep,hist.borrow_dep]),errors='coerce')
    top=max(60,float(ys.max())*1.1 if ys.notna().any() else 60)
    fig=go.Figure();_base(fig,threshold,top)
    others=[c for c in order if c not in colors and c in cur.index]
    gx,gy,gt=[],[],[]
    for c in others:
        x,y,arrow,v=_xy(cur.loc[c])
        if x is None or y is None:continue
        gx.append(x);gy.append(y);gt.append(f'{c}<br>이자보상배율† {number(v,"배")}<br>차입금 의존도 {number(y)}')
    if gx:
        fig.add_trace(go.Scatter(x=gx,y=gy,mode='markers',name=f'그 외 선택 기업 {len(gx)}곳 (회색)',
            marker=dict(size=8,color=cs.GRAY,line=dict(color='#fff',width=1)),text=gt,hovertemplate='%{text}<extra></extra>'))
    show=[] if trail=='현재 위치만' else [target] if trail=='심사 대상만' else list(colors)
    labels=[]
    for c,color in colors.items():
        h=metrics[metrics.corp_name==c].set_index('period').reindex(PERIODS[:PERIODS.index(period)+1])
        if c in show:
            pts=[(p,)+_xy(h.loc[p]) for p in h.index if valid(h.loc[p].icr) and valid(h.loc[p].borrow_dep)]
            fy=[q for q in pts if 'H' not in q[0]]
            fig.add_trace(go.Scatter(x=[q[1] for q in fy],y=[q[2] for q in fy],mode='lines+markers+text',
                line=dict(color=color,width=2),marker=dict(size=8,color='#fff',line=dict(color=color,width=2),
                    symbol=['triangle-left' if q[3]=='←' else 'triangle-right' if q[3]=='→' else 'circle' for q in fy]),
                text=[(SHORT[q[0]]+(' '+q[3]+' '+number(q[4],'배',1) if q[3] else '')) if q[0]!=period else '' for q in fy],
                textposition=['bottom center' if k%2==0 else 'top center' for k in range(len(fy))],
                textfont=dict(size=10,color=color),showlegend=False,cliponaxis=False,
                customdata=[[q[0],number(q[4],'배'),number(q[2])] for q in fy],
                hovertemplate=c+' · %{customdata[0]}<br>이자보상배율† %{customdata[1]}<br>차입금 의존도 %{customdata[2]}<extra></extra>'))
            if period=='2026H1' and len(pts)>=2 and pts[-1][0]=='2026H1' and pts[-2][0]=='2025':
                fig.add_trace(go.Scatter(x=[pts[-2][1],pts[-1][1]],y=[pts[-2][2],pts[-1][2]],mode='lines',
                    line=dict(color=color,width=2,dash='dot'),showlegend=False,hoverinfo='skip'))
        if c not in cur.index:continue
        x,y,arrow,v=_xy(cur.loc[c])
        if x is None or y is None:continue
        half='H' in period
        fig.add_trace(go.Scatter(x=[x],y=[y],mode='markers',name=c+(' ◀ 심사 대상' if c==target else ''),
            marker=dict(size=18 if c==target else 14,color='#fff' if half else color,symbol='diamond' if half else 'circle',
                line=dict(color=color,width=3)),
            customdata=[[cs.X_LABEL[period],number(v,'배'),number(y)]],
            hovertemplate=c+' · %{customdata[0]}<br>이자보상배율† %{customdata[1]}<br>차입금 의존도 %{customdata[2]}<extra></extra>'))
        labels.append((y,x,c,color,arrow,v))
    # 이름표: 세로 위치 순으로 위/아래 번갈아 배치해 겹침 완화
    for i,(y,x,c,color,arrow,v) in enumerate(sorted(labels,reverse=True)):
        side=-1 if x>HI-4 else 1
        fig.add_annotation(x=x,y=y,ax=side*(46+(i%2)*26),ay=-34 if i%2==0 else 34,
            text=f'<b>{c}</b><br>{arrow+" " if arrow else ""}{number(v,"배")} · {number(y,"%",1)}',
            showarrow=True,arrowhead=0,arrowwidth=1,arrowcolor=color,font=dict(size=12,color=color),
            bgcolor='rgba(255,255,255,.92)',bordercolor=color,borderwidth=1,borderpad=3,xanchor='left' if side>0 else 'right')
    title=(f'<b>여신 관리 지도 · {cs.X_LABEL[period]}</b><br><span style="font-size:12px;color:#6b7a8c">'
           '가로 = 이자를 감당하는 힘, 세로 = 빚 비중 · 오른쪽 아래(초록)일수록 여유, 왼쪽 위(빨강)일수록 집중 관리</span>')
    _layout(fig,title,top,height=600)
    return fig

def stress_figure(name,before_icr,after_icr,borrow,before_stage,after_stage,scenario,threshold,unchanged_note=''):
    """스트레스 결과: 현재 vs 시나리오 이자보상배율 가로 막대. 차입금 의존도는 고정이라 1차원으로 보여 준다."""
    vals=[v for v in (before_icr,after_icr) if valid(v)]
    lo=min([0]+vals);hi=max([3]+vals)
    pad=(hi-lo)*.18
    fig=go.Figure()
    fig.add_shape(type='rect',x0=lo-pad,x1=1,y0=-.6,y1=1.6,fillcolor='#FFE3E3',line_width=0,layer='below')
    fig.add_shape(type='rect',x0=1,x1=hi+pad,y0=-.6,y1=1.6,fillcolor='#EBFBEE',line_width=0,layer='below')
    fig.add_annotation(x=lo-pad,y=1.6,xanchor='left',yanchor='top',showarrow=False,
        text='<b>1배 미만</b>: 영업이익으로 이자를 다 못 냄',font=dict(size=12,color='#C92A2A'))
    fig.add_annotation(x=hi+pad,y=1.6,xanchor='right',yanchor='top',showarrow=False,
        text='<b>1배 이상</b>: 영업이익으로 이자 감당',font=dict(size=12,color='#2B8A3E'))
    rows=[('시나리오',after_icr,after_stage),('현재',before_icr,before_stage)]
    for label,v,stg in rows:
        if not valid(v):continue
        fig.add_trace(go.Bar(y=[label],x=[v],orientation='h',width=.5,
            marker=dict(color=STAGE_COLORS[stg],pattern=dict(shape='/' if label=='시나리오' else '',fgcolor='#fff',size=8)),
            hovertemplate=label+' %{x:.2f}배<extra></extra>',showlegend=False))
        fig.add_annotation(x=v,y=label,xanchor='left' if v>=0 else 'right',xshift=6 if v>=0 else -6,showarrow=False,
            text=f'<b>{number(v,"배")}</b> · {stg}',font=dict(size=14,color=STAGE_COLORS[stg]),bgcolor='rgba(255,255,255,.95)',borderpad=3)
    fig.add_vline(x=1,line=dict(color='#212529',width=2,dash='dash'))
    fig.add_vline(x=0,line=dict(color='#adb5bd',width=1))
    if valid(before_icr) and valid(after_icr) and abs(after_icr-before_icr)>1e-9:
        fig.add_annotation(x=after_icr,y=0.32,ax=before_icr,ay=0.68,xref='x',yref='y',axref='x',ayref='y',
            showarrow=True,arrowhead=3,arrowsize=1.3,arrowwidth=2,arrowcolor='#343a40',text='')
    if unchanged_note:
        fig.add_annotation(x=(1+hi+pad)/2,y=.5,showarrow=False,text=unchanged_note,
            font=dict(size=12,color='#495057'),bgcolor='#fff',bordercolor='#adb5bd',borderwidth=1,borderpad=5)
    fig.update_layout(title=dict(text=f'<b>스트레스 시나리오 · {name}</b><br><span style="font-size:12px;color:#6b7a8c">'
            f'{scenario} · 차입금 의존도 {number(borrow,"%",1)} 고정 (참고선 {threshold:g}%)</span>',x=0,font=dict(size=16,color=cs.INK)),
        height=300,margin=dict(l=80,r=150,t=84,b=50),paper_bgcolor='#fff',plot_bgcolor='#fff',bargap=.4,
        xaxis=dict(range=[lo-pad,hi+pad],fixedrange=True,zeroline=False,gridcolor=cs.GRID,
            title=dict(text='이자보상배율† (배) · 점선 = 1배',font=dict(size=12))),
        yaxis=dict(fixedrange=True,tickfont=dict(size=14,color=cs.INK),range=[-.6,1.6]))
    return fig

def render_bank(metrics,quarterly,events,quality,companies,period,target,colors,threshold,coverage=None):
    current=metrics[(metrics.corp_name.isin(companies))&(metrics.period==period)]
    st.subheader('여신 계기판 · 지금 확인할 신호')
    st.caption('관리 단계(참고) · 기준선은 실제 은행 심사 기준이 아닙니다 · 투자 권유 아님')
    st.caption('† 이자비용 계정이 없으면 금융원가로 대체합니다. 금융원가에는 외환손실 등도 포함될 수 있어 실제 이자보상배율과 다릅니다. 기업별 분모는 심사 메모와 데이터 기준에서 확인하세요.')
    no_data=[n for n in companies if current[current.corp_name==n].empty]
    for name in companies:
        h=current[current.corp_name==name]
        if h.empty:continue
        r=h.iloc[0];s=management(r,quality,threshold)
        streak=loss_streak(metrics.to_dict('records'),name,period)
        tags=flags(r,metrics,quarterly,events)
        if s=='판정 보류' and not quality.empty:
            issue=quality[(quality.corp_name==name)&(quality.period==period)]
            if not issue.empty:tags.append('보류 이유: '+str(issue.iloc[0]['status']))
        if streak>=3:tags.append(f'한계기업 참고조건 · 연간 {streak}년 연속 1배 미만')
        dot='●' if valid(r.icr) and r.icr<1 else '○' if valid(r.icr) else '-'
        st.markdown(f'<div class="credit-row" style="border-left-color:{STAGE_COLORS[s]}"><div class="credit-name">{escape(name)}</div>'
            f'<div class="credit-values">{dot} 이자 {number(r.icr,"배")} <span>차입 {number(r.borrow_dep)}</span></div>'
            f'<div class="credit-stage" style="color:{STAGE_COLORS[s]}">{s}</div>'
            f'<div class="credit-flags">{escape(" · ".join(tags) or "확인된 해당 플래그 없음")}</div></div>',unsafe_allow_html=True)
    if no_data:
        st.info(f'{period} 자료가 없는 선택 기업 {len(no_data)}곳은 위 판정·아래 지도에서 제외했습니다: '+', '.join(no_data[:8])+(' 외' if len(no_data)>8 else ''))
        with st.expander(f'자료 없는 기업 {len(no_data)}곳 · 최신 제공 자료 보기'):
            for name in no_data:
                available=metrics[metrics.corp_name==name].copy()
                if available.empty:
                    st.caption(missing_message(name,period,coverage,metrics));continue
                available['_end']=available.period.map(lambda p:p[:4]+('-06' if 'H' in p else '-12'))
                latest=available.sort_values('_end').iloc[-1]
                with st.container(border=True):
                    st.markdown('**'+name+' · 최신 제공 자료 '+str(latest.period)+'**')
                    st.caption(str(period)+' 자료는 확인되지 않아 별도 기간을 표시합니다. 현재 기간의 비교지도·순위에는 포함하지 않습니다.')
                    cols=st.columns(3)
                    for col,title,key in zip(cols,['매출액','영업이익','당기순이익'],['revenue','op_income','net_income']):col.metric(title,number(latest[key]/1e8,'억원'))
                    cols=st.columns(3)
                    for col,title,key in zip(cols,['자산','부채','자본'],['assets','liabilities','equity']):col.metric(title,number(latest[key]/1e8,'억원'))
                    st.write('영업이익률 '+number(latest.op_margin)+' · 부채비율 '+number(latest.debt_ratio))
                    st.caption('해당 기간 관리 단계: '+management(latest,quality,threshold)+' · '+('상반기 누적' if 'H' in str(latest.period) else '연간')+' · '+str(latest.fs_div))
                    hit=quality[(quality.corp_name==name)&(quality.period==latest.period)]
                    if not hit.empty and hit.iloc[0].source_url:st.link_button('제공 자료의 DART 원문',hit.iloc[0].source_url)
    st.caption('한계기업 참고조건은 금융원가 대체 여부를 포함한 지표상 신호입니다. 법적·공식 분류가 아닙니다. H1은 추가 연도로 세지 않습니다.')
    st.subheader('여신 관리 지도 · 지나온 길과 현재 위치')
    trail=st.radio('지나온 길 표시',['심사 대상만','색으로 강조한 기업 모두','현재 위치만'],horizontal=True,key='map_trail')
    st.plotly_chart(credit_map(metrics,companies,period,threshold,target,trail),width='stretch',key='credit_map')
    st.caption(f'점선 = 참고선(이자보상배율 1배, 차입금 의존도 {threshold:g}%) · 색·이름표는 심사 대상 포함 최대 {cs.MAX_HIGHLIGHT}곳, 나머지는 회색 점(마우스를 올리면 이름) · '
               "궤적의 '21~'25 = 연간, 빈 마름모·점선 = 2026 상반기 · 축 밖 값은 가장자리에 화살표(→ ←)와 실제 배율 표시 · †금융원가 기준")
    missing=current[current.icr.isna()|current.borrow_dep.isna()]
    if len(missing):st.info('지도 좌표가 없는 기업: '+', '.join(missing.corp_name))
    hit=current[current.corp_name==target]
    st.subheader(f'헤드룸과 스트레스 · {target}')
    st.caption('시나리오 값, 원본 아님(metrics.csv 값으로 계산). 차입금 의존도는 고정합니다.')
    if hit.empty:
        st.info('선택한 기간의 심사 대상 데이터가 없습니다. 다른 기간을 선택해 주세요.')
    else:
        r=hit.iloc[0];h=headroom(r.icr)
        a,b=st.columns([1,2])
        with a:
            if h is not None:
                st.metric('기준선까지 이익 감소 여력',number(h))
                st.caption('분모가 고정되면 이 비율만큼 영업이익이 감소할 때 1배에 도달합니다.')
            elif valid(r.icr):st.warning('기준선 아래' if r.icr<1 else '기준선 도달 · 감소 여력 없음')
            else:st.info('이자보상배율 자료 없음')
        with b:
            decrease=st.slider('영업이익 감소 (%)',0,50,0,5,key='stress_profit')/100
            increase=st.slider('이자비용·금융원가 증가 (%)',0,30,0,5,key='stress_interest')/100
            mode=st.radio('충격 적용 방식',['슬라이더','2022년 같은 충격이 다시 오면'],horizontal=True)
        hist=None;available=True
        if mode.startswith('2022'):
            annual=metrics[metrics.corp_name==target].set_index('period')
            if '2021' not in annual.index or '2022' not in annual.index or not valid(annual.loc['2021'].op_income) or annual.loc['2021'].op_income<=0 or not valid(annual.loc['2022'].op_income):
                available=False;st.info('양수인 2021년 영업이익과 2022년 영업이익이 있어야 과거 충격을 적용할 수 있습니다.')
            else:
                hist=annual.loc['2022'].op_income/annual.loc['2021'].op_income-1
                st.caption('실제 2021→2022 영업이익 변화율 '+number(hist*100)+'를 적용합니다. 이 모드에서는 두 슬라이더가 적용되지 않습니다.')
        if available:
            new=stress(r.icr,r.op_income,decrease,increase if hist is None else 0,hist)
            if valid(r.op_income) and r.op_income<=0:st.info('이미 영업적자 또는 영업이익 0: 감소율을 적용하지 않고 현재 위치를 유지합니다.')
            simulated=r.copy();simulated['icr']=new
            before=management(r,quality,threshold);after=management(simulated,quality,threshold)
            c1,c2,c3=st.columns(3)
            c1.metric('현재 이자보상배율†',number(r.icr,'배'))
            c2.metric('시나리오 이자보상배율†',number(new,'배'),
                      None if not (valid(new) and valid(r.icr)) else f'{new-r.icr:+.2f}배')
            c3.metric('관리 단계',after,'변화 없음' if before==after else f'{before} → {after}',delta_color='off')
            st.write('시나리오 대응: '+RESPONSES[after])
            if hist is not None: scen=f'2022년 같은 충격: 영업이익 {hist*100:+.1f}%'
            else: scen=f'영업이익 {-round(decrease*100):+d}%, 이자비용·금융원가 {round(increase*100):+d}%'.replace('+0%','0%')
            note=''
            if valid(r.op_income) and r.op_income<=0: note='이미 영업적자 → 감소율 미적용, 위치 변화 없음'
            elif valid(new) and valid(r.icr) and abs(new-r.icr)<1e-9: note='충격 0% → 현재와 같음 · 위 슬라이더로 충격을 넣어 보세요'
            st.plotly_chart(stress_figure(target,r.icr,new,r.borrow_dep,before,after,scen,threshold,note),width='stretch',key='stress_map')
    render_review(target,period)  # 주석·산업 확인 (review_checklist.csv, 수기 정리 + 출처)
    st.subheader('심사 메모 · 숫자에서 점검 항목으로')
    for _,r in current.iterrows():
        s=management(r,quality,threshold)
        with st.expander(f'{r.corp_name} · {s}',expanded=r.corp_name==target):
            st.write('Q1 수익성: 영업이익률 '+number(r.op_margin)+' · ROA '+number(r.roa)+' · ROE '+number(r.roe))
            st.write('Q2 이자 부담: 이자보상배율† '+number(r.icr,'배')+' · 분모 '+str(r.get('icr_basis','확인 필요')))
            st.write('Q3 재무 부담: 차입금 의존도 '+number(r.borrow_dep)+' · 부채비율 '+number(r.debt_ratio))
            st.write('Q4 관리 단계(참고): '+s+' · '+RESPONSES[s])
            tags=flags(r,metrics,quarterly,events)
            if tags:st.caption('주의 표시: '+' / '.join(tags))
            if str(r.period)=='2026H1':st.markdown('[원료 조달 점검 근거: 산업통상부 발표]('+SOURCE_RISK+') · 업종 공통 위험이며 개별 기업의 피해를 확정하지 않습니다.')
            if not events.empty:
                end=str(r.period)[:4]+('-06-30' if 'H' in str(r.period) else '-12-31')
                ev=events[(events.corp_name==r.corp_name)&(events.date<=end)].sort_values('date',ascending=False).head(3)
                for _,e in ev.iterrows():st.markdown(f'[{e.date} · {e.event}]({e.source_url})')
    st.subheader('실제 사례 · 약정 기준과 참고선의 차이')
    with st.container(border=True):
        st.markdown('**롯데케미칼 회사채 재무특약 조정**')
        st.write('회사는 2024년 11월, 회사채 약정의 3개년 누적 EBITDA/이자비용 5배 유지 조건을 충족하지 못했다고 발표했습니다. 12월에는 사채권자 집회에서 재무특약 조정이 승인됐고, 롯데월드타워를 활용한 은행 보증을 설명했습니다.')
        st.markdown('[회사 발표 · 2024-11-21](https://www.lottechem.com/ko/media/news/1012/view.do) · [특약 조정 · 2024-12-19](https://www.lottechem.com/ko/media/news/1025/view.do)')
        st.write('실제 5배 약정과 이 앱의 1배 참고선은 다릅니다. EBITDA/이자비용과 영업이익/금융원가를 같은 지표로 해석할 수 없습니다.')
        rr=metrics[(metrics.corp_name=='롯데케미칼')&(metrics.period=='2024')]
        if not rr.empty:st.caption('2024 연간 지표의 지도 위치: '+management(rr.iloc[0],quality,threshold)+' (연말 공시이며 약정 위반 당시 분기와도 기준일이 다릅니다.)')
        st.markdown('[대산 사업재편 관련 금융위원회 발표 · 2026-02-25](https://www.fsc.go.kr/no010101/86328)')
