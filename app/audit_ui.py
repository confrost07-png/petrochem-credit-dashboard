"""공시 원문 연간 화면. 결산월이 다른 기간은 같은 비교표에 섞지 않는다."""
import pandas as pd
import plotly.express as px
import streamlit as st
from credit_ui import management,number

def render_audit(metrics,quality,companies,period,target,threshold,data):
    metrics=metrics.copy()
    metrics['fiscal_end']=metrics.get('fiscal_end',pd.Series(index=metrics.index,dtype=str)).fillna(metrics.period.map(lambda p:p[:4]+('-06' if 'H' in p else '-12')))
    tabs=st.tabs(['은행 판단','근거 지표','충격 분기','데이터 기준'])
    selected=metrics[metrics.corp_name.isin(companies)&(metrics.period==period)]
    missing=set(companies)-set(selected.corp_name)
    with tabs[0]:
        st.subheader('공시 원문으로 확인한 재무 자료')
        st.info('감사보고서·사업보고서·반기보고서 원문에서 추출했습니다. 같은 기간끼리 비교하며 연간·반기는 구분합니다.')
        for _,r in selected.iterrows():
            with st.container(border=True):
                a,b,c=st.columns([2,2,2])
                a.markdown('**'+r.corp_name+'**');a.caption(r.fiscal_end+' 기준 · '+('상반기 누적 · ' if r.period_type=='H1' else '연간 · ')+('연결' if r.fs_div=='CFS' else '별도'))
                b.write('이자보상배율† '+number(r.icr,'배'));b.write('차입금 의존도 '+number(r.borrow_dep))
                c.markdown('**'+management(r,quality,threshold)+'**')
                hit=quality[(quality.corp_name==r.corp_name)&(quality.period==r.period)]
                if not hit.empty:st.caption(hit.iloc[0].status)
                st.caption('이자보상배율 분모: '+r.icr_basis)
                st.link_button('DART 공시 원문',r.source_url)
        for name in missing:st.caption(name+' · 선택한 결산기간의 원문 수치 없음. 기업별 제공 기간을 선택해 주세요.')
        st.caption('핵심 재무 수치가 확인되어도 차입금·이자 계정이 불완전하면 관리 단계는 보류합니다. 투자 권유 아님.')
    with tabs[1]:
        st.subheader(period+' 재무지표')
        if not selected.empty:
            name=st.selectbox('KPI 카드 기업',selected.corp_name.tolist())
            r=selected[selected.corp_name==name].iloc[0]
            st.caption(name+' · '+r.fiscal_end+' 결산 · 원화 금액은 억원으로 표시')
            fields=[('매출액','revenue','억원'),('영업이익','op_income','억원'),('당기순이익','net_income','억원'),('자산','assets','억원'),('부채','liabilities','억원'),('자본','equity','억원')]
            cols=st.columns(3)
            for i,(title,key,unit) in enumerate(fields):cols[i%3].metric(title,number(r[key]/1e8,unit))
            cols=st.columns(3)
            for i,(title,key) in enumerate([('매출 성장률','sales_growth'),('영업이익률','op_margin'),('부채비율','debt_ratio'),('ROA','roa'),('ROE','roe'),('차입금 의존도','borrow_dep')]):cols[i%3].metric(title,number(r[key]))
            if r.period_type=='FY':st.caption('ROA: 평균자산 사용. ROE: 별도 순이익/평균자본; 연결 지배주주 계정 미확인 시 표시하지 않습니다.')
            if r.period_type=='H1':st.info('반기 ROA·ROE는 순이익을 2배로 연환산하고 기말 자산·자본으로 나눕니다. 성장률은 전년 반기 누적 대비입니다.')
            table=selected[['corp_name','period','fiscal_end','fs_div','revenue','op_income','net_income','assets','liabilities','equity','sales_growth','op_margin','debt_ratio','roa','roe','icr','borrow_dep']].copy()
            for key in ['revenue','op_income','net_income','assets','liabilities','equity']:table[key]=table[key]/1e8
            table=table.rename(columns={'corp_name':'기업','period':'기간','fiscal_end':'결산월','fs_div':'연결/별도','revenue':'매출(억원)','op_income':'영업이익(억원)','net_income':'순이익(억원)','assets':'자산(억원)','liabilities':'부채(억원)','equity':'자본(억원)','sales_growth':'성장률(%)','op_margin':'영업이익률(%)','debt_ratio':'부채비율(%)','borrow_dep':'차입 의존도(%)'})
            st.dataframe(table,hide_index=True,width='stretch')
            chart=selected[['corp_name','revenue','op_income']].melt(id_vars='corp_name',var_name='지표',value_name='억원');chart['억원']/=1e8
            st.plotly_chart(px.bar(chart,x='corp_name',y='억원',color='지표',barmode='group',labels={'corp_name':'기업'},title='동일 결산기간 기업 비교'),width='stretch')
            # 결산월별로 추이를 구분한다. 3월 결산과 12월 결산을 이어 그리지 않는다.
            history=metrics[metrics.corp_name.isin(companies)].copy()
            history=history[history.period_type.eq(r.period_type)]
            history['결산월']=history.fiscal_end.str[-2:]
            st.plotly_chart(px.line(history.sort_values('fiscal_end'),x='fiscal_end',y='op_margin',color='corp_name',facet_row='결산월',markers=True,labels={'fiscal_end':'결산기간','op_margin':'영업이익률(%)','corp_name':'기업'},title='결산월별 연도 추이'),width='stretch')
            st.subheader('분석 결과')
            st.write('영업이익률 '+number(r.op_margin)+' · 부채비율 '+number(r.debt_ratio)+' · 매출 성장률 '+number(r.sales_growth))
            st.caption('성장률은 같은 결산월의 전기 대비입니다. 재무제표 기준과 사업 구조 차이를 함께 확인하세요.')
    with tabs[2]:
        st.subheader('충격 분기')
        st.info('현재 이 경로에는 연간 공시 원문만 있습니다. 연간 수치를 분기 실적으로 변환하지 않습니다. 분기 시연은 사이드바에서 “재무제표 API”를 선택하세요.')
    with tabs[3]:
        st.subheader('원문 추출 근거')
        st.caption('원화 단위 변환, 당기·전기 열 구분, 자산=부채+자본 검산을 통과한 본표만 metrics.csv에 반영했습니다. 천원·백만원 표의 등식 오차 허용 범위는 원문 표시 단위 한 단위입니다.')
        st.dataframe(quality[quality.corp_name.isin(companies)],hide_index=True,width='stretch')
        path=data/'audit_account_mapping.csv'
        if path.exists():
            mapping=pd.read_csv(path,dtype={'stock_code':str,'rcept_no':str})
            st.dataframe(mapping[mapping.corp_name.isin(companies)],hide_index=True,width='stretch')
        for fn in ['audit_report_index.csv','audit_extraction_status.csv','audit_account_mapping.csv','metrics.csv']:
            path=data/fn
            if path.exists():st.download_button(fn,path.read_bytes(),file_name=fn,mime='text/csv',key='audit_'+fn)
        st.caption('미확인 계정은 0으로 채우지 않습니다. 연결 ROE는 지배주주 계정 확인 전 보류합니다.')
