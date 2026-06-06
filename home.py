"""원스글로벌 회계 인사이트 — Notion 영업현황 DB 기반 회계 관점 대시보드."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

import contracts as ct
from data_loader import explode_services, load_sales_data

# ============== Palette ==============
PRIMARY = "#5B43C9"
PRIMARY_DARK = "#4A35B0"
PRIMARY_LIGHT = "#F1EEFB"
ACCENT = "#10B981"
WARN = "#F59E0B"
DANGER = "#E84C3D"

STATE_COLORS = {
    "리드": "#D6CFEC",
    "제안": "#B5A4DE",
    "협상": "#9379D1",
    "성공": PRIMARY,
    "입금완료": PRIMARY_DARK,
    "정산완료": ACCENT,
    "실패": DANGER,
}

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
    .kpi-box.success {{ border-left: 4px solid {ACCENT}; }}
    .kpi-box.success .kpi-value {{ color: {ACCENT}; }}

    /* Alert cards (horizontal row, auto) */
    .alert-row {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 12px;
        margin: 18px 0 4px;
    }}
    .alert-card {{
        background: #FFF6F4;
        border-left: 4px solid {DANGER};
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 0.86rem;
        color: #1F1E29;
        display: flex; gap: 10px; align-items: flex-start;
    }}
    .alert-card.warn {{ background: #FFF8EC; border-left-color: {WARN}; }}
    .alert-card .alert-icon {{ font-size: 1.05rem; flex-shrink: 0; line-height: 1.3; }}
    .alert-card .alert-title {{ font-weight: 700; display: block; margin-bottom: 2px; }}
    .alert-card .alert-body {{ color: #2A2440; line-height: 1.4; }}

    /* Insight grid (bottom) */
    .insight-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 12px;
        margin: 6px 0 18px;
    }}
    .insight-card {{
        background: {PRIMARY_LIGHT};
        border: 1px solid #E0D7F5;
        border-radius: 10px;
        padding: 14px 18px;
        font-size: 0.88rem;
        color: #2A2440;
    }}
    .insight-card .ic-head {{
        font-weight: 700;
        color: {PRIMARY_DARK};
        margin-bottom: 6px;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }}
    .insight-card .ic-body {{ line-height: 1.45; }}
    .insight-empty {{
        background: #F7FBF7;
        border: 1px solid #D7EBDB;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        color: #2D5A38;
        font-size: 0.9rem;
        margin: 6px 0 18px;
    }}

    /* Section meta line (gray small caption under h2) */
    .sec-meta {{ color: #8B8995; font-size: 0.78rem; margin: -4px 0 10px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============== 헤더 ==============
st.markdown(
    f'<div class="top-header">'
    f'<div class="top-logo">🏠 홈</div>'
    f'<div class="top-tag">Onesglobal Internal</div>'
    f'<div style="flex:1;"></div>'
    f'<div style="color:rgba(255,255,255,0.85);font-size:0.85rem;">'
    f'데이터 출처: Notion 2026 영업현황 DB'
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

# ============== 사이드바 필터 ==============
st.sidebar.header("🔧 필터")

# 노션 영업현황은 계약일 기준만 의미 있음 (세금계산서 발행/입금은 시트에서 관리)
date_col = "계약일"
min_date = df[date_col].min()
max_date = df[date_col].max()
if pd.isna(min_date) or pd.isna(max_date):
    min_date = pd.Timestamp("2026-01-01")
    max_date = pd.Timestamp.now()

date_range = st.sidebar.date_input(
    "계약일 범위",
    value=(min_date.date(), max_date.date()),
    min_value=min_date.date(),
    max_value=max_date.date(),
)

status_filter = st.sidebar.multiselect(
    "상태",
    options=["리드", "제안", "협상", "성공", "입금완료", "정산완료", "실패"],
    default=["성공", "입금완료", "정산완료", "협상", "제안"],
)
nr_filter = st.sidebar.multiselect(
    "신규/갱신",
    options=["신규", "갱신", "일회성"],
    default=["신규", "갱신", "일회성"],
)
all_services = sorted({s for row in df["서비스명"] for s in row})
svc_filter = st.sidebar.multiselect("서비스명", options=all_services)

st.sidebar.divider()
st.sidebar.caption(f"전체 {len(df)}건 / 캐시 10분")
if st.sidebar.button("🔄 캐시 새로고침"):
    st.cache_data.clear()
    st.rerun()

# ============== 필터 적용 ==============
fdf = df.copy()
if status_filter:
    fdf = fdf[fdf["상태"].isin(status_filter)]
if nr_filter:
    fdf = fdf[fdf["신규갱신"].isin(nr_filter)]
if svc_filter:
    fdf = fdf[fdf["서비스명"].apply(lambda lst: any(s in lst for s in svc_filter))]

if len(date_range) == 2:
    start, end = date_range
    in_range = (fdf[date_col].notna()) & (fdf[date_col].dt.date >= start) & (fdf[date_col].dt.date <= end)
    fdf_period = fdf[in_range].copy()
else:
    fdf_period = fdf.copy()

# ============== 집계 ==============
# 발행/입금 관련 데이터는 회계관리 페이지(시트 기반)로 분리됨.
# 홈에서는 노션의 영업 파이프라인 관점만 다룸.
confirmed_states = ("성공", "입금완료", "정산완료")
potential_states = ("리드", "제안", "협상")

confirmed = fdf[fdf["상태"].isin(confirmed_states)]
potential = fdf[fdf["상태"].isin(potential_states)]
_today = pd.Timestamp.today().normalize()

# ============== 핵심 KPI ==============
st.markdown("## ⭐ 핵심 지표")
st.markdown('<div class="sec-meta">필터·기간 조건 적용 결과</div>', unsafe_allow_html=True)


def kpi_card(label, value, sub="", danger=False, success=False):
    cls = "kpi-box"
    if danger:
        cls += " danger"
    elif success:
        cls += " success"
    return (
        f'<div class="{cls}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


c1, c2, c3 = st.columns(3)
c1.markdown(
    kpi_card(
        "전체 파이프라인",
        f"{len(fdf):,}건",
        f"총 매출 가치 {fdf['총매출'].sum()/1e8:.2f}억",
    ),
    unsafe_allow_html=True,
)
c2.markdown(
    kpi_card(
        "확정 매출",
        f"{confirmed['총매출'].sum()/1e8:.2f}억",
        f"{len(confirmed)}건 · 성공·입금·정산",
        success=True,
    ),
    unsafe_allow_html=True,
)
c3.markdown(
    kpi_card(
        "잠재 매출",
        f"{potential['총매출'].sum()/1e8:.2f}억",
        f"{len(potential)}건 · 리드·제안·협상",
    ),
    unsafe_allow_html=True,
)

# ============== 상단 알림 (자동 생성) ==============
# 미수금·발행 누락 알림은 회계관리(시트 기반) 페이지로 이동했음.
# 홈은 영업 데이터 정합성 알림만 유지.
top_alerts = []

not_filled_n = int(confirmed["정산유형"].isna().sum())
not_filled_amount = float(confirmed.loc[confirmed["정산유형"].isna(), "총매출"].sum())
if not_filled_n > 0:
    top_alerts.append({
        "title": "정산유형 미입력",
        "body": f"<b>{not_filled_n}건</b> ({not_filled_amount/1e8:.2f}억) · 노션 DB 정합성 점검 필요",
        "warn": True,
    })

nr_agg = (
    confirmed.groupby("신규갱신")
    .agg(건수=("name", "count"), 매출=("총매출", "sum"))
    .reset_index()
)
nr_pivot = nr_agg.set_index("신규갱신") if not nr_agg.empty else None
ren_ratio = None
if nr_pivot is not None and "신규" in nr_pivot.index and "갱신" in nr_pivot.index:
    new_unit = nr_pivot.loc["신규", "매출"] / nr_pivot.loc["신규", "건수"]
    ren_unit = nr_pivot.loc["갱신", "매출"] / nr_pivot.loc["갱신", "건수"]
    if new_unit > 0:
        ren_ratio = ren_unit / new_unit
        if ren_ratio < 0.5:
            top_alerts.append({
                "title": "갱신 단가 저하",
                "body": f"갱신 평균 단가가 신규 대비 <b>{ren_ratio*100:.0f}%</b> · 다운셀·할인 관행 검토",
                "warn": True,
            })

if top_alerts:
    cards_html = ""
    for a in top_alerts:
        cls = "alert-card warn" if a["warn"] else "alert-card"
        cards_html += (
            f'<div class="{cls}">'
            f'<div class="alert-icon">⚠️</div>'
            f'<div><span class="alert-title">{a["title"]}</span>'
            f'<span class="alert-body">{a["body"]}</span></div>'
            f'</div>'
        )
    st.markdown(f"<div class='alert-row'>{cards_html}</div>", unsafe_allow_html=True)

st.info(
    "🚨 **미수금 상세 · 세금계산서 발행 누락은 [회계 관리 페이지](./회계_관리)에서 확인하세요** "
    "(좌측 사이드바). 회수 우선순위·경과일 추적 가능."
)

# ============== 매출 추이 ==============
# 데이터 소스: Google Sheets payments.발행일 (계약 관리·회계 관리와 동일)
# → 계약 관리에서 회차별 발행일 입력하면 즉시 반영
st.markdown("## 📅 매출 추이")
hdr_cols = st.columns([6, 4])
with hdr_cols[0]:
    st.markdown(
        '<div class="sec-meta">계약 관리 시트 발행일 기준 · 단가 합계</div>',
        unsafe_allow_html=True,
    )
with hdr_cols[1]:
    period_unit = st.radio(
        "기간 단위",
        options=["연별", "분기별", "월별", "일별"],
        index=2,
        horizontal=True,
        label_visibility="collapsed",
        key="revenue_period_unit",
    )

import plotly.graph_objects as go

UNIT_MAP = {
    "일별": {"freq": "D",  "fmt": "%Y-%m-%d"},
    "월별": {"freq": "M",  "fmt": "%Y-%m"},
    "분기별": {"freq": "Q", "fmt": None},
    "연별": {"freq": "Y",  "fmt": "%Y"},
}
unit_cfg = UNIT_MAP[period_unit]

# Google Sheets payments + contracts 로드 — 발행일 set인 회차의 단가 합산
# (노션상태가 강등된 계약은 filter_active_contracts로 제외)
try:
    payments_df = ct.load_payments()
    contracts_for_unit = ct.filter_active_contracts(ct.load_contracts())
except Exception as e:
    payments_df = pd.DataFrame()
    contracts_for_unit = pd.DataFrame()
    st.warning(f"⚠️ 계약 관리 시트 로드 실패: {str(e)[:120]}")

if not payments_df.empty and not contracts_for_unit.empty:
    # 활성 계약의 payment만 대상으로 단가 join
    active_pay = payments_df[payments_df["contract_id"].isin(contracts_for_unit["contract_id"])]
    billed = active_pay.merge(
        contracts_for_unit[["contract_id", "단가"]],
        on="contract_id",
        how="left",
    )
    billed = billed[billed["발행일"].notna()].copy()
    billed["단가"] = pd.to_numeric(billed["단가"], errors="coerce").fillna(0)
else:
    billed = pd.DataFrame()
# 사이드바 date_range가 발행일 기간을 의미할 때만 적용 (period_basis와 무관하게 그대로 사용)
if not billed.empty and len(date_range) == 2:
    start, end = date_range
    billed = billed[
        (billed["발행일"].dt.date >= start) & (billed["발행일"].dt.date <= end)
    ]

if billed.empty:
    st.info(
        "기간 내 세금계산서 발행 회차가 없습니다. "
        "계약 관리에서 회차별 발행일을 입력하면 여기에 반영됩니다."
    )
else:
    # 연도별 비교가 가능한 그룹 막대 — 월별/분기별일 때 연도별 색 분리
    billed["년도"] = billed["발행일"].dt.year.astype(str)

    # 연도별 컬러 팔레트 (가장 최근 연도 = 진보라, 이전 연도들은 다른 톤)
    _years = sorted(billed["년도"].unique())
    _year_palette = ["#F59E0B", PRIMARY, ACCENT, PRIMARY_DARK, "#0EA5E9"]
    _color_map = {y: _year_palette[i % len(_year_palette)] for i, y in enumerate(_years)}

    if period_unit == "월별":
        billed["월"] = billed["발행일"].dt.month
        agg = billed.groupby(["월", "년도"])["단가"].sum().reset_index()
        fig = px.bar(
            agg, x="월", y="단가", color="년도",
            color_discrete_map=_color_map, barmode="group",
            labels={"단가": "매출 (원)", "월": "", "년도": ""},
            text="단가",
        )
        fig.update_xaxes(
            tickmode="array", tickvals=list(range(1, 13)),
            ticktext=[f"{m}월" for m in range(1, 13)],
        )
    elif period_unit == "분기별":
        billed["분기"] = billed["발행일"].dt.quarter
        agg = billed.groupby(["분기", "년도"])["단가"].sum().reset_index()
        fig = px.bar(
            agg, x="분기", y="단가", color="년도",
            color_discrete_map=_color_map, barmode="group",
            labels={"단가": "매출 (원)", "분기": "", "년도": ""},
            text="단가",
        )
        fig.update_xaxes(
            tickmode="array", tickvals=[1, 2, 3, 4],
            ticktext=["Q1", "Q2", "Q3", "Q4"],
        )
    elif period_unit == "연별":
        agg = billed.groupby("년도")["단가"].sum().reset_index()
        fig = px.bar(
            agg, x="년도", y="단가",
            color="년도", color_discrete_map=_color_map,
            labels={"단가": "매출 (원)", "년도": ""},
            text="단가",
        )
    else:  # 일별
        billed["일"] = billed["발행일"].dt.date
        agg = billed.groupby("일")["단가"].sum().reset_index()
        fig = px.bar(
            agg, x="일", y="단가",
            color_discrete_sequence=[PRIMARY],
            labels={"단가": "매출 (원)", "일": ""},
        )

    fig.update_traces(
        marker_line_width=0,
        texttemplate="%{text:,.0f}",
        textposition="outside",
        textfont=dict(size=10),
        cliponaxis=False,
    )
    fig.update_layout(
        height=420,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Pretendard, Malgun Gothic, 맑은 고딕, sans-serif",
                  size=12, color="#1E1B2E"),
        showlegend=(period_unit in ("월별", "분기별")),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            x=1.0, xanchor="right",
            bgcolor="rgba(255,255,255,0.85)",
            font=dict(size=11),
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#F0EFF5",
            showline=False, zeroline=False, title="",
            separatethousands=True,
        ),
        bargap=0.18, bargroupgap=0.08,
        hoverlabel=dict(bgcolor="white", bordercolor="#E5E5E8",
                        font=dict(family="Pretendard, sans-serif", size=12)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    total_issued = agg["단가"].sum()
    st.caption(f"누적 발행 매출: **{total_issued:,.0f}원** · {total_issued/1e8:.2f}억")

# ============== 영업 파이프라인 ==============
st.markdown("## 🎯 영업 파이프라인")
st.markdown(
    '<div class="sec-meta">상태별 분포 — 건수 / 매출</div>',
    unsafe_allow_html=True,
)

state_order = ["리드", "제안", "협상", "성공", "입금완료", "정산완료", "실패"]
state_agg = fdf.groupby("상태").agg(건수=("name", "count"), 매출=("총매출", "sum")).reset_index()
state_agg["상태"] = pd.Categorical(state_agg["상태"], categories=state_order, ordered=True)
state_agg = state_agg.sort_values("상태")


def _state_chart(y_col, label):
    fig = px.bar(
        state_agg, x="상태", y=y_col,
        color="상태", color_discrete_map=STATE_COLORS,
        labels={y_col: label, "상태": ""},
    )
    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white",
        showlegend=False,
        yaxis=dict(showgrid=True, gridcolor="#F0EFF5", title=""),
        xaxis=dict(title=""),
        font=dict(family="Pretendard, sans-serif", size=12),
    )
    fig.update_traces(marker_line_width=0)
    return fig


col_a, col_b = st.columns(2)
with col_a:
    st.caption("상태별 건수")
    st.plotly_chart(_state_chart("건수", "건수"), use_container_width=True)
with col_b:
    st.caption("상태별 매출")
    st.plotly_chart(_state_chart("매출", "매출 (원)"), use_container_width=True)

# ============== 서비스별 매출 ==============
st.markdown("## 💎 서비스별 매출")
st.markdown(
    '<div class="sec-meta">확정 건만 — 상위 15개</div>',
    unsafe_allow_html=True,
)

confirmed_exp = explode_services(confirmed)
svc_agg = (
    confirmed_exp.groupby("서비스명")
    .agg(건수=("name", "count"), 매출=("총매출", "sum"))
    .reset_index()
    .sort_values("매출", ascending=False)
    .head(15)
)

if not svc_agg.empty:
    fig = px.bar(
        svc_agg.sort_values("매출"),
        y="서비스명", x="매출",
        orientation="h",
        labels={"매출": "매출 (원)", "서비스명": ""},
        color_discrete_sequence=[PRIMARY],
        text="매출",
    )
    fig.update_traces(
        texttemplate="%{text:,.0f}", textposition="outside",
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>매출 %{x:,.0f}원<extra></extra>",
    )
    fig.update_layout(
        height=max(340, 28 * len(svc_agg)),
        margin=dict(l=0, r=100, t=10, b=0),
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#F0EFF5", title=""),
        yaxis=dict(title=""),
        font=dict(family="Pretendard, sans-serif", size=12),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("확정 매출 데이터 없음.")

# ============== 신규 vs 갱신 vs 일회성 ==============
st.markdown("## 🆕 신규 · 갱신 · 일회성")
st.markdown(
    '<div class="sec-meta">확정 건 — 매출 비중 / 평균 단가</div>',
    unsafe_allow_html=True,
)

if not nr_agg.empty:
    nr_agg["평균단가"] = (nr_agg["매출"] / nr_agg["건수"]).round(0)
    col_x, col_y = st.columns([2, 3])
    with col_x:
        fig = px.pie(
            nr_agg, values="매출", names="신규갱신", hole=0.55,
            color="신규갱신",
            color_discrete_map={"신규": PRIMARY, "갱신": PRIMARY_DARK, "일회성": ACCENT},
        )
        fig.update_traces(
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>매출 %{value:,.0f}원<br>비중 %{percent}<extra></extra>",
        )
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            font=dict(family="Pretendard, sans-serif", size=12),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    with col_y:
        st.dataframe(
            nr_agg,
            column_config={
                "신규갱신": st.column_config.TextColumn("구분"),
                "건수": st.column_config.NumberColumn("건수", format="localized"),
                "매출": st.column_config.NumberColumn("매출 (원)", format="localized"),
                "평균단가": st.column_config.NumberColumn("평균단가 (원)", format="localized"),
            },
            hide_index=True,
            use_container_width=True,
        )

# ============== 정산유형별 ==============
st.markdown("## 💳 정산유형별")
st.markdown('<div class="sec-meta">확정 건 — 건수 / 매출</div>', unsafe_allow_html=True)

st_agg = (
    confirmed.groupby("정산유형", dropna=False)
    .agg(건수=("name", "count"), 매출=("총매출", "sum"))
    .reset_index()
)
st_agg["정산유형"] = st_agg["정산유형"].fillna("(미입력)")
st.dataframe(
    st_agg.sort_values("건수", ascending=False).reset_index(drop=True),
    column_config={
        "정산유형": st.column_config.TextColumn("정산유형"),
        "건수": st.column_config.NumberColumn("건수", format="localized"),
        "매출": st.column_config.NumberColumn("매출 (원)", format="localized"),
    },
    hide_index=True,
    use_container_width=True,
)

# 계약 → 발행 지연 섹션은 회계관리 페이지(시트 기반)로 이동했음

# ============== 계약 관리 페이지 안내 ==============
st.info(
    "💼 **계약 상세는 [계약 관리 페이지](./계약_관리)에서 확인하세요** "
    "(좌측 사이드바). 고객별 계약·결제 회차·입금 추적 가능."
)

# ============== 종합 인사이트 ==============
st.markdown("## 🔍 종합 인사이트")
st.markdown(
    '<div class="sec-meta">자동 생성 — 임계치 초과 항목만 표시</div>',
    unsafe_allow_html=True,
)

insights = []

# 미수금·발행 누락·발행 지연 인사이트는 회계관리 페이지(시트 기반)로 이동.
# 홈은 영업 지표 인사이트만 유지.

if not nr_agg.empty:
    new_row = nr_agg[nr_agg["신규갱신"] == "신규"]
    if not new_row.empty:
        total_conf = confirmed["총매출"].sum()
        if total_conf > 0:
            new_pct = new_row["매출"].iloc[0] / total_conf * 100
            if new_pct > 60:
                insights.append({
                    "title": "신규 매출 의존도",
                    "body": f"확정 매출의 {new_pct:.0f}%가 신규 — 갱신 매출 비중 확대 전략 검토.",
                })

if not_filled_n > 0:
    insights.append({
        "title": "데이터 정합성",
        "body": f"정산유형 미입력 {not_filled_n}건 ({not_filled_amount/1e8:.2f}억) — 노션 DB 점검.",
    })

if ren_ratio is not None and ren_ratio < 0.7:
    insights.append({
        "title": "갱신 단가 모니터링",
        "body": f"갱신 평균이 신규의 {ren_ratio*100:.0f}% — 만기 협상 시 가격 방어 필요.",
    })

if insights:
    grid_html = "<div class='insight-grid'>"
    for ins in insights:
        grid_html += (
            f'<div class="insight-card">'
            f'<div class="ic-head">💡 {ins["title"]}</div>'
            f'<div class="ic-body">{ins["body"]}</div></div>'
        )
    grid_html += "</div>"
    st.markdown(grid_html, unsafe_allow_html=True)
else:
    st.markdown(
        "<div class='insight-empty'>✅ 주요 경보 없음 · 데이터 양호</div>",
        unsafe_allow_html=True,
    )

# ============== 푸터 ==============
st.markdown("---")
st.caption(
    f"마지막 조회: {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
    f"출처: Notion 2026 영업현황 DB"
)
