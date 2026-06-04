"""원스글로벌 회계 관리 — 미수금 · 세금계산서 발행 누락."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from data_loader import load_sales_data

# ============== Palette ==============
PRIMARY = "#5B43C9"
PRIMARY_DARK = "#4A35B0"
PRIMARY_LIGHT = "#F1EEFB"
ACCENT = "#10B981"
WARN = "#F59E0B"
DANGER = "#E84C3D"

st.set_page_config(
    page_title="회계 관리 · 원스글로벌",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============== CSS ==============
st.markdown(
    f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, *, [class*="css"], button, input, select, textarea {{
        font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', -apple-system, sans-serif !important;
    }}
    .stApp {{ background: white; padding-top: 64px; padding-bottom: 0 !important; }}
    [data-testid="stAppViewContainer"] {{ background: white !important; }}
    body, html {{ background: white !important; }}
    [data-testid="stHeader"], header[data-testid="stHeader"],
    div[data-testid="stToolbar"] {{
        display: none !important; height: 0 !important; visibility: hidden !important;
    }}
    section[data-testid="stSidebar"] {{ top: 64px !important; }}
    .top-header {{
        background: linear-gradient(90deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        padding: 0 32px;
        display: flex; align-items: center; gap: 20px;
        color: white !important;
        position: fixed; top: 0; left: 0;
        width: 100vw; height: 64px;
        z-index: 999999;
        box-shadow: 0 1px 4px rgba(91, 67, 201, 0.15);
    }}
    .top-header * {{ color: white !important; }}
    .top-logo {{ font-size: 1.2rem; font-weight: 800; display: flex; align-items: center; gap: 8px; }}
    .top-tag {{
        background: rgba(255,255,255,0.2); padding: 4px 10px;
        border-radius: 4px; font-size: 0.7rem; font-weight: 500;
    }}
    section[data-testid="stMain"] {{ background: white !important; }}
    [data-testid="stMainBlockContainer"] {{
        max-width: 1280px !important;
        padding-left: 24px !important; padding-right: 24px !important;
        padding-top: 24px !important;
    }}
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {{
        background: #FFFFFF !important;
        border-right: 1px solid #EDECF1 !important;
    }}
    h1, h2, h3, h4 {{ color: #1E1B2E; }}
    h2 {{
        margin-top: 36px !important;
        border-bottom: 2px solid {PRIMARY_LIGHT};
        padding-bottom: 8px;
        font-size: 1.2rem !important;
        font-weight: 700 !important;
    }}

    /* KPI cards */
    .kpi-box {{
        background: white;
        border: 1px solid #EDECF1;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 4px rgba(91,67,201,0.04);
        transition: box-shadow 0.2s ease, transform 0.2s ease;
        min-height: 108px;
    }}
    .kpi-box:hover {{
        box-shadow: 0 4px 14px rgba(91,67,201,0.12);
        transform: translateY(-1px);
    }}
    .kpi-label {{
        color: #6B6A73;
        font-size: 0.74rem;
        margin-bottom: 8px;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }}
    .kpi-value {{
        color: {PRIMARY};
        font-size: 1.7rem;
        font-weight: 800;
        line-height: 1.1;
    }}
    .kpi-sub {{ color: #B0AFB8; font-size: 0.78rem; margin-top: 6px; }}
    .kpi-box.danger {{ border-left: 4px solid {DANGER}; }}
    .kpi-box.danger .kpi-value {{ color: {DANGER}; }}
    .kpi-box.warn {{ border-left: 4px solid {WARN}; }}
    .kpi-box.warn .kpi-value {{ color: {WARN}; }}

    .sec-meta {{ color: #8B8995; font-size: 0.78rem; margin: -4px 0 10px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============== 헤더 ==============
st.markdown(
    f'<div class="top-header">'
    f'<div class="top-logo">🚨 회계 관리</div>'
    f'<div class="top-tag">Onesglobal Internal</div>'
    f'<div style="flex:1;"></div>'
    f'<div style="color:rgba(255,255,255,0.85);font-size:0.85rem;">'
    f'미수금 · 발행 누락 추적'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ============== 데이터 로드 ==============
try:
    df = load_sales_data()
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.stop()

if df.empty:
    st.warning("DB에 데이터가 없습니다.")
    st.stop()

# ============== 사이드바 (검색 + 새로고침) ==============
st.sidebar.header("🔧 검색")
search_query = st.sidebar.text_input(
    "고객명 / 건명 키워드",
    value="",
    placeholder="예: 박**병원, ConnectCare",
    help="고객기관·건명에서 부분 일치 검색 (대소문자 무시)",
).strip()

st.sidebar.divider()
st.sidebar.caption(f"전체 {len(df)}건 / 캐시 10분")
if st.sidebar.button("🔄 캐시 새로고침"):
    st.cache_data.clear()
    st.rerun()


def _apply_search(d: pd.DataFrame) -> pd.DataFrame:
    if not search_query:
        return d
    q = search_query.lower()

    def _hit(row):
        for col in ("고객기관", "name"):
            v = row.get(col, "")
            if v and q in str(v).lower():
                return True
        return False

    return d[d.apply(_hit, axis=1)]


# ============== 집계 ==============
_today = pd.Timestamp.today().normalize()
confirmed_states = ("성공", "입금완료", "정산완료")

unpaid_all = df[(df["세금계산서발행일"].notna()) & (~df["입금완료"])]
overdue_all = df[
    (df["계약일"].notna())
    & (df["계약일"] <= _today)
    & (df["세금계산서발행일"].isna())
    & (df["상태"].isin(confirmed_states))
].copy()
if not overdue_all.empty:
    overdue_all["경과일"] = (_today - overdue_all["계약일"]).dt.days

unpaid = _apply_search(unpaid_all)
overdue_issue = _apply_search(overdue_all)

# ============== KPI ==============
total_unpaid = float(unpaid["총매출"].sum())
total_overdue = float(overdue_issue["총매출"].sum())
total_risk = total_unpaid + total_overdue


def kpi_card(label, value, sub="", danger=False, warn=False):
    cls = "kpi-box"
    if danger:
        cls += " danger"
    elif warn:
        cls += " warn"
    return (
        f'<div class="{cls}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


c1, c2, c3 = st.columns(3)
c1.markdown(
    kpi_card(
        "미수금",
        f"{total_unpaid/1e8:.2f}억",
        f"{len(unpaid)}건 · 발행 완료 / 입금 X",
        danger=True,
    ),
    unsafe_allow_html=True,
)
c2.markdown(
    kpi_card(
        "발행 누락",
        f"{total_overdue/1e8:.2f}억",
        f"{len(overdue_issue)}건 · 계약일 경과 / 발행 X",
        warn=True,
    ),
    unsafe_allow_html=True,
)
c3.markdown(
    kpi_card(
        "회수 리스크 합계",
        f"{total_risk/1e8:.2f}억",
        f"{len(unpaid)+len(overdue_issue)}건 · 미수금 + 발행 누락",
    ),
    unsafe_allow_html=True,
)

# ============== 미수금 상세 ==============
st.markdown("## 🚨 미수금 상세")
st.markdown(
    '<div class="sec-meta">세금계산서 발행 완료 · 입금 미완료 — 발행일 오름차순</div>',
    unsafe_allow_html=True,
)

if unpaid_all.empty:
    st.success("미수금 없음. ✅")
elif unpaid.empty:
    st.info(f"'{search_query}' 검색 결과 없음 (전체 미수금 {len(unpaid_all)}건).")
else:
    unpaid_view = unpaid[["세금계산서발행일", "고객기관", "name", "총매출", "상태", "url"]].copy()
    unpaid_view.columns = ["발행일", "고객기관", "건명", "금액", "상태", "Notion"]
    unpaid_view = unpaid_view.sort_values("발행일", ascending=True).reset_index(drop=True)
    st.dataframe(
        unpaid_view,
        column_config={
            "발행일": st.column_config.DateColumn("발행일", format="YYYY-MM-DD"),
            "고객기관": st.column_config.TextColumn("고객기관"),
            "건명": st.column_config.TextColumn("건명"),
            "금액": st.column_config.NumberColumn("금액 (원)", format="localized"),
            "상태": st.column_config.TextColumn("상태"),
            "Notion": st.column_config.LinkColumn("Notion", display_text="열기"),
        },
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        f"합계: **{unpaid['총매출'].sum():,.0f}원** · {len(unpaid)}건 · "
        f"평균 {unpaid['총매출'].mean():,.0f}원"
    )
    # 단일 고객 집중도 경고
    if unpaid["총매출"].sum() > 0:
        top_pct = unpaid["총매출"].max() / unpaid["총매출"].sum() * 100
        if top_pct > 50:
            top_row = unpaid.loc[unpaid["총매출"].idxmax()]
            name = top_row["고객기관"] or top_row["name"]
            st.warning(
                f"⚠️ 단일 고객 집중 위험: **{name}** 1건이 미수금의 **{top_pct:.0f}%** — 우선 회수 권장."
            )

# ============== 세금계산서 발행 누락 ==============
st.markdown("## 📝 세금계산서 발행 누락")
st.markdown(
    '<div class="sec-meta">계약일 경과 · 발행 미완료 (확정 건 한정) — 경과일 내림차순</div>',
    unsafe_allow_html=True,
)

if overdue_all.empty:
    st.success("발행 누락 없음. ✅")
elif overdue_issue.empty:
    st.info(f"'{search_query}' 검색 결과 없음 (전체 발행 누락 {len(overdue_all)}건).")
else:
    over_view = overdue_issue[[
        "계약일", "경과일", "고객기관", "name", "총매출", "상태", "url",
    ]].copy()
    over_view.columns = ["계약일", "경과일", "고객기관", "건명", "금액", "상태", "Notion"]
    over_view = over_view.sort_values("경과일", ascending=False).reset_index(drop=True)
    st.dataframe(
        over_view,
        column_config={
            "계약일": st.column_config.DateColumn("계약일", format="YYYY-MM-DD"),
            "경과일": st.column_config.NumberColumn("경과일", format="%d일"),
            "고객기관": st.column_config.TextColumn("고객기관"),
            "건명": st.column_config.TextColumn("건명"),
            "금액": st.column_config.NumberColumn("금액 (원)", format="localized"),
            "상태": st.column_config.TextColumn("상태"),
            "Notion": st.column_config.LinkColumn("Notion", display_text="열기"),
        },
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        f"합계: **{overdue_issue['총매출'].sum():,.0f}원** · {len(overdue_issue)}건 · "
        f"최장 경과 {int(overdue_issue['경과일'].max())}일"
    )

# ============== 푸터 ==============
st.markdown("---")
st.caption(
    f"마지막 조회: {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
    f"출처: Notion 2026 영업현황 DB"
)
