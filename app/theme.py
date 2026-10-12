"""화면 테마: KB 노란색과 따뜻한 회색. 디자인만 변경.

원칙
- 네이비는 머리글·탭·섹션 선·버튼에만 쓴다.
- 본문은 흰색·회색 무채색. 색은 관리 단계(빨강·주황·초록)와 기업 고유색에만 남긴다.
- 카드는 모서리 4px, 얇은 테두리, 그림자 없음.
- 글꼴은 바꾸지 않는다 (Noto Sans KR 그대로).
이 파일은 색·모양만 바꾸며 수치·계산에는 영향이 없다.
"""

NAVY = "#FFBC00"       # 머리글·탭·버튼
NAVY_DARK = "#504B43"  # 머리글 띠 배경
NAVY_SOFT = "#FFF5D6"  # 강조 배경(옅은 네이비)
INK = "#33302B"        # 본문 글자
MUTED = "#706B63"      # 보조 글자
LINE = "#E5E0D7"       # 테두리·구분선
BG = "#F7F6F2"         # 페이지 배경
RADIUS = "12px"

CSS = f"""
<style>
:root {{--ink:{INK};--muted:{MUTED};--line:{LINE};--bg:{BG};--navy:{NAVY}}}
[data-testid="stAppViewContainer"] {{background:{BG}!important}}
[data-testid="stSidebar"] {{background:#fff!important;border-right:1px solid {LINE}!important}}
/* 비교 기업 태그: 네이비 바탕 + 흰 글자 (태그 배경은 config.toml primaryColor) */
[data-testid="stSidebar"] [data-testid="stMultiSelect"] .react-aria-ComboBox span {{color:{INK}!important;border-radius:3px}}

/* 머리글: 네이비 띠 */
.page-head {{background:{NAVY_DARK};border-radius:{RADIUS};padding:26px 30px 22px!important;margin-bottom:14px;
  border-bottom:4px solid {NAVY}}}
.page-head h1 {{color:#fff!important}}
.page-head p,.page-head p b,.page-head strong {{color:#F7F3EA!important}}
.page-head .source-line {{color:#EAE2D5!important}}
.page-head .eyebrow {{background:transparent!important;color:#EAE2D5!important;border:1px solid #8C8171;
  border-radius:3px!important;letter-spacing:.12em}}

/* 탭 */
[data-testid="stTabs"] [role="tablist"] {{border-bottom:1px solid {LINE}!important;gap:4px!important}}
[data-testid="stTabs"] [role="tab"] {{color:{MUTED}!important;border-radius:0!important}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{color:{INK}!important;border-bottom:3px solid {NAVY}!important;
  background:#fff!important}}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{background:{NAVY}!important}}

/* 카드·차트·표: 각진 모서리, 얇은 테두리, 그림자 없음 */
[data-testid="stMetric"],[data-testid="stDataFrame"],[data-testid="stPlotlyChart"],
[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stExpander"] details,
.summary-card,.credit-row,.helper-box,.chat-box,.chat-answer {{border-radius:{RADIUS}!important;box-shadow:none!important}}
[data-testid="stMetric"],[data-testid="stDataFrame"],[data-testid="stPlotlyChart"] {{border:1px solid {LINE}!important;background:#fff}}
[data-testid="stMetricLabel"] {{color:{MUTED}!important}}

/* 섹션 머리: 네이비 굵은 선 + 번호 */
.section-kicker {{color:{INK}!important;border-top:3px solid {NAVY};padding-top:10px;width:100%;letter-spacing:.08em!important}}
h2,h3 {{color:{INK}!important}}

/* 안내 상자: 무채색 + 네이비 왼쪽 선 */
.helper-box {{background:#fff!important;border:1px solid {LINE}!important;border-left:4px solid {NAVY}!important;color:{INK}!important}}

/* 여신 계기판 행: 왼쪽 띠 색 = 관리 단계 (credit_ui에서 지정) */
.credit-row {{border-top:1px solid {LINE}!important;border-right:1px solid {LINE}!important;border-bottom:1px solid {LINE}!important;
  border-left-width:6px!important;border-left-style:solid!important}}
.credit-flags {{color:{MUTED}!important}}

/* 요약 카드 */
.summary-card {{border:1px solid {LINE}!important;border-top:4px solid var(--accent)!important}}

/* 버튼·챗봇: 네이비 */
.stButton button[kind="primary"],[data-testid="stFormSubmitButton"] button,
.st-key-floating_chat button {{background:{NAVY}!important;border-color:{INK}!important;color:#fff!important}}
.st-key-floating_chat button {{border-radius:4px!important;box-shadow:0 4px 14px rgba(18,35,64,.25)!important}}
.st-key-floating_chat button:hover {{background:#E5AA00!important}}
.chat-box {{background:#fff!important;border:1px solid {LINE}!important;border-top:4px solid {NAVY}!important}}
.chat-box .chat-title {{color:{INK}!important}}
.chat-box .chat-sub,.chat-box .chat-legal {{color:{MUTED}!important}}
.chat-box .chat-status {{background:{NAVY}!important;border-radius:3px!important}}
.chat-answer {{border-color:{LINE}!important;color:{INK}!important}}

/* RM 인사이트: 노랑 → 네이비 */
.ins-label {{color:{INK}!important}}
.ins-bar {{background:{NAVY}!important;border-radius:0!important;width:48px!important;height:4px!important}}
.ins-sub {{color:{MUTED}!important}}
.ins-row,.rm {{border-radius:{RADIUS}!important;border-color:{LINE}!important}}
.ins-n {{background:{NAVY}!important;color:{INK}!important;border-radius:3px!important}}
.rm .ic {{background:{NAVY_SOFT}!important;border-radius:3px!important}}
.rm .cap {{color:{INK}!important}}
.rm .hl {{background:{NAVY_SOFT}!important;color:{INK}!important}}
.rm .bar {{border-radius:3px!important}}
.rm .bar.key {{background:{NAVY_SOFT}!important}}
.peer-t {{border-radius:{RADIUS}!important;border:1px solid {LINE}}}
.limit {{background:{NAVY_DARK}!important;border-radius:{RADIUS}!important}}
.limit b {{color:#fff!important}}

/* KB palette: dark text on yellow, generous whitespace, clear selection. */
.page-head {{border-bottom:5px solid {NAVY};border-radius:16px!important;padding:28px 32px!important}}
.page-head .eyebrow {{color:#FFCE43!important;border-color:#8C8171!important}}
[data-testid="stMetric"] {{border-top:3px solid {NAVY}!important;padding:18px!important}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{background:{NAVY_SOFT}!important;border-radius:8px 8px 0 0!important}}
[data-testid="stSidebar"] [data-baseweb="tag"] {{background:{NAVY_SOFT}!important;color:{INK}!important}}
[data-testid="stSidebar"] [data-baseweb="tag"] * {{color:{INK}!important}}
[data-testid="stSidebar"] [data-testid="stImage"] {{max-width:150px;margin:0 0 16px}}
.chat-box .chat-status {{color:{INK}!important}}
.st-key-floating_chat button *,[data-testid="stFormSubmitButton"] button * {{color:{INK}!important}}
.st-key-floating_chat button {{border-radius:999px!important;box-shadow:0 6px 20px rgba(80,75,67,.18)!important}}
.section-kicker {{border-top-color:{NAVY}!important}}
[data-testid="stAlert"][data-baseweb="notification"] {{border-radius:10px}}
@media(max-width:720px){{.page-head{{padding:20px!important}}}}
/* Gallery-inspired financial workspace: pills, compact header and spacious cards. */
:root {{--ink:#302F35;--muted:#777983;--line:#ECECF0;--bg:#F6F6F8}}
[data-testid="stAppViewContainer"] {{background:#F6F6F8!important}}
.block-container {{max-width:1500px;padding-top:2rem;padding-bottom:7rem}}
[data-testid="stSidebar"] {{border-right:1px solid #ECECF0!important}}
[data-testid="stSidebar"] h3 {{font-size:1.1rem!important;margin-bottom:12px}}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{background:#F5F5F7;border-radius:12px!important;border-color:#E9E9ED}}
[data-testid="stSidebar"] [data-baseweb="tag"] {{border-radius:999px!important;background:#FFF2C2!important}}
.page-head {{background:#fff!important;border:1px solid #ECECF0!important;border-bottom:0!important;border-radius:20px!important;padding:26px 30px!important}}
.page-head h1 {{color:#302F35!important;font-size:clamp(29px,3vw,42px)!important;margin:12px 0 14px}}
.page-head p,.page-head p b,.page-head strong {{color:#55565E!important}}
.page-head .source-line {{color:#878891!important;font-size:12px!important;line-height:1.8}}
.page-head .eyebrow {{background:#FFF3CC!important;color:#806000!important;border:0!important;border-radius:999px!important;padding:7px 12px}}
[data-testid="stTabs"] [role="tablist"] {{background:#EBEBEF;padding:5px!important;border:0!important;border-radius:14px;gap:4px!important;margin:16px 0 24px}}
[data-testid="stTabs"] [role="tab"] {{padding:10px 18px!important;font-size:14px!important;border:0!important;border-radius:10px!important;color:#777983!important}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{background:#fff!important;color:#302F35!important;border:0!important;border-radius:10px!important;box-shadow:0 2px 6px rgba(30,30,40,.06)!important}}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{display:none}}
[data-testid="stMetric"] {{border:1px solid #ECECF0!important;border-radius:18px!important;padding:20px!important}}
[data-testid="stMetricValue"] {{font-size:clamp(24px,2.3vw,34px)!important;color:#302F35!important}}
[data-testid="stMetricLabel"] {{font-size:13px;color:#777983!important}}
[data-testid="stPlotlyChart"] {{border:1px solid #ECECF0!important;border-radius:20px!important;padding:14px 16px 6px;box-shadow:0 3px 16px rgba(32,33,45,.025)!important;margin-bottom:14px}}
[data-testid="stDataFrame"] {{border:1px solid #ECECF0!important;border-radius:16px!important}}
h2 {{margin-top:24px!important}} h3 {{margin-top:20px!important}}
.section-kicker {{border:0!important;padding:0!important;color:#7A7C85!important;letter-spacing:.08em!important;margin-top:28px!important}}
.credit-row,.summary-card,.ins-row,.rm {{border-radius:16px!important;padding:20px!important;border-color:#ECECF0!important}}
.credit-row {{gap:12px;margin:12px 0!important}}
.credit-values {{font-size:16px}} .credit-flags {{line-height:1.7;color:#85868F!important}}
.helper-box {{background:#FFF9E8!important;border:0!important;border-left:3px solid #FFBC00!important;border-radius:12px!important}}
[data-testid="stExpander"] details {{border-radius:14px!important;border-color:#ECECF0!important}}
.chat-box,.chat-answer {{border-radius:16px!important}}
.st-key-floating_chat button {{background:#FFCB38!important;border-color:#FFCB38!important;color:#302F35!important}}
.rm .ic,.ins-n {{border-radius:12px!important}} .ins-bar {{border-radius:999px!important}}
@media(max-width:900px){{[data-testid="stPlotlyChart"]{{padding:6px 4px}} [data-testid="stTabs"] [role="tab"]{{padding:9px 12px!important}} .credit-row{{grid-template-columns:1fr!important}}}}
@media(max-width:1100px){{
  [data-testid="stMain"] [data-testid="stHorizontalBlock"]{{flex-wrap:wrap!important}}
  [data-testid="stMain"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{{flex:1 1 280px!important;width:auto!important;min-width:min(280px,100%)!important}}
}}
</style>
"""
