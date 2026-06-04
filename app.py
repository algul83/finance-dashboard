"""원스글로벌 회계 인사이트 — Notion 영업현황 DB 기반 회계 관점 대시보드."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import explode_services, load_sales_data


def classify_contract(row) -> str:
    """신규/갱신 + 정산유형 → 계약 타입.
    - 일회성 계약: 신규/갱신='일회성'
    - 구독 (1회 선납): 신규·갱신 + 1회정산
    - 구독 (월납): 신규·갱신 + 매월정산
    - 구독 (분납): 신규·갱신 + 분할정산
    - 구독 (정산유형 미입력): 신규·갱신 + 정산유형 미입력
    """
    nr = row.get("신규갱신")
    st_type = row.get("정산유형")
    if nr == "일회성":
        return "일회성 계약"
    if nr in ("신규", "갱신"):
        if st_type == "1회정산":
            return "구독 (1회 선납)"
        if st_type == "매월정산":
            return "구독 (월납)"
        if st_type == "분할정산":
            return "구독 (분납)"
        return "구독 (정산유형 미입력)"
    return "분류 불명"


CONTRACT_TYPE_ORDER = [
    "일회성 계약",
    "구독 (1회 선납)",
    "구독 (월납)",
    "구독 (분납)",
    "구독 (정산유형 미입력)",
    "분류 불명",
]
CONTRACT_TYPE_EMOJI = {
    "일회성 계약": "🎫",
    "구독 (1회 선납)": "💰",
    "구독 (월납)": "📆",
    "구독 (분납)": "🧩",
    "구독 (정산유형 미입력)": "⚠️",
    "분류 불명": "❓",
}

# ============== 색상 (원스글로벌 통일 팔레트) ==============
PRIMARY = "#5B43C9"
PRIMARY_DARK = "#4A35B0"
PRIMARY_LIGHT = "#F1EEFB"
ACCENT = "#10B981"
WARN = "#F59E0B"
DANGER = "#E84C3D"

st.set_page_config(
    page_title="원스글로벌 회계 인사이트",
    page_icon="💰",
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
    h2 {{ margin-top: 36px !important; border-bottom: 2px solid {PRIMARY_LIGHT}; padding-bottom: 8px; }}
    .kpi-box {{
        background: white; border: 1px solid #EDECF1;
        border-radius: 12px; padding: 16px 18px;
        box-shadow: 0 1px 4px rgba(91,67,201,0.04);
    }}
    .kpi-label {{ color: #6B6A73; font-size: 0.82rem; margin-bottom: 6px; }}
    .kpi-value {{ color: {PRIMARY}; font-size: 1.5rem; font-weight: 800; }}
    .kpi-sub {{ color: #B0AFB8; font-size: 0.78rem; margin-top: 4px; }}
    .alert-box {{
        background: #FFF6F4; border-left: 4px solid {DANGER};
        padding: 14px 18px; border-radius: 6px; margin: 12px 0;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============== 헤더 ==============
st.markdown(
    f'<div class="top-header">'
    f'<div class="top-logo">💰 회계 인사이트</div>'
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

# 기간 (계약일 또는 세금계산서 발행일)
period_basis = st.sidebar.radio(
    "기간 기준",
    options=["세금계산서발행일", "계약일"],
    index=0,
    horizontal=True,
)
date_col = period_basis
min_date = df[date_col].min()
max_date = df[date_col].max()
if pd.isna(min_date) or pd.isna(max_date):
    min_date = pd.Timestamp("2026-01-01")
    max_date = pd.Timestamp.now()

date_range = st.sidebar.date_input(
    f"{period_basis} 범위",
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

# 서비스명 필터
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

# 기간 필터 (기간 기준 컬럼이 채워진 행만)
if len(date_range) == 2:
    start, end = date_range
    in_range = (fdf[date_col].notna()) & (fdf[date_col].dt.date >= start) & (fdf[date_col].dt.date <= end)
    # 기간 필터는 핵심 지표용 — 미수금 등은 전체에서 본다. 두 갈래로 운용.
    fdf_period = fdf[in_range].copy()
else:
    fdf_period = fdf.copy()

# ============== 핵심 KPI ==============
st.markdown(f"## ⭐ 핵심 지표 (필터 적용)")

confirmed_states = ("성공", "입금완료", "정산완료")
potential_states = ("리드", "제안", "협상")

confirmed = fdf[fdf["상태"].isin(confirmed_states)]
potential = fdf[fdf["상태"].isin(potential_states)]
unpaid = fdf[(fdf["세금계산서발행일"].notna()) & (~fdf["입금완료"])]

c1, c2, c3, c4 = st.columns(4)
c1.markdown(
    f'<div class="kpi-box"><div class="kpi-label">전체 파이프라인</div>'
    f'<div class="kpi-value">{len(fdf):,}건</div>'
    f'<div class="kpi-sub">총 매출 가치 {fdf["총매출"].sum()/1e8:.2f}억</div></div>',
    unsafe_allow_html=True,
)
c2.markdown(
    f'<div class="kpi-box"><div class="kpi-label">확정 매출 (성공+입금+정산)</div>'
    f'<div class="kpi-value">{confirmed["총매출"].sum()/1e8:.2f}억</div>'
    f'<div class="kpi-sub">{len(confirmed)}건</div></div>',
    unsafe_allow_html=True,
)
c3.markdown(
    f'<div class="kpi-box"><div class="kpi-label">잠재 매출 (리드~협상)</div>'
    f'<div class="kpi-value">{potential["총매출"].sum()/1e8:.2f}억</div>'
    f'<div class="kpi-sub">{len(potential)}건</div></div>',
    unsafe_allow_html=True,
)
c4.markdown(
    f'<div class="kpi-box" style="border-left: 4px solid {DANGER};">'
    f'<div class="kpi-label">⚠️ 미수금 (발행 / 입금X)</div>'
    f'<div class="kpi-value" style="color:{DANGER};">{unpaid["총매출"].sum()/1e8:.2f}억</div>'
    f'<div class="kpi-sub">{len(unpaid)}건</div></div>',
    unsafe_allow_html=True,
)

# ============== 미수금 상세 ==============
st.markdown("## 🚨 미수금 상세 (세금계산서 발행 / 입금 미완료)")

if unpaid.empty:
    st.success("미수금 없음. ✅")
else:
    unpaid_view = unpaid[["세금계산서발행일", "고객기관", "name", "총매출", "상태", "url"]].copy()
    unpaid_view.columns = ["발행일", "고객기관", "건명", "금액", "상태", "Notion"]
    unpaid_view = unpaid_view.sort_values("발행일")
    unpaid_view["금액"] = unpaid_view["금액"].apply(lambda v: f"{v:,.0f}원")
    unpaid_view["발행일"] = unpaid_view["발행일"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        unpaid_view,
        column_config={
            "Notion": st.column_config.LinkColumn("Notion", display_text="열기"),
        },
        hide_index=True,
        use_container_width=True,
    )
    # 단일 고객 집중도 경고
    top_unpaid_pct = (unpaid["총매출"].max() / unpaid["총매출"].sum() * 100) if unpaid["총매출"].sum() else 0
    if top_unpaid_pct > 50:
        top_row = unpaid.loc[unpaid["총매출"].idxmax()]
        st.markdown(
            f'<div class="alert-box">⚠️ <b>단일 고객 집중 위험</b>: '
            f'{top_row["고객기관"] or top_row["name"]} 1건이 미수금의 '
            f'<b>{top_unpaid_pct:.1f}%</b>를 차지합니다. 우선 회수 권장.</div>',
            unsafe_allow_html=True,
        )

# ============== 월별 매출 ==============
st.markdown("## 📅 월별 세금계산서 발행 매출")

monthly = fdf[fdf["세금계산서발행일"].notna()].copy()
monthly["월"] = monthly["세금계산서발행일"].dt.to_period("M").astype(str)
month_agg = monthly.groupby("월").agg(건수=("name", "count"), 매출=("총매출", "sum")).reset_index()

if not month_agg.empty:
    fig = px.bar(
        month_agg, x="월", y="매출", text="매출",
        labels={"매출": "매출 (원)"},
        color_discrete_sequence=[PRIMARY],
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=20, b=0),
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(showgrid=True, gridcolor="#F0EFF5"),
    )
    st.plotly_chart(fig, use_container_width=True)
    total_issued = month_agg["매출"].sum()
    st.caption(f"누적 발행 매출: **{total_issued:,.0f}원** ({total_issued/1e8:.2f}억)")
else:
    st.info("기간 내 세금계산서 발행 건이 없습니다.")

# ============== 영업 파이프라인 상태별 ==============
st.markdown("## 🎯 영업 파이프라인 상태별 분포")

state_order = ["리드", "제안", "협상", "성공", "입금완료", "정산완료", "실패"]
state_agg = fdf.groupby("상태").agg(건수=("name", "count"), 매출=("총매출", "sum")).reset_index()
state_agg["상태"] = pd.Categorical(state_agg["상태"], categories=state_order, ordered=True)
state_agg = state_agg.sort_values("상태")

col_a, col_b = st.columns(2)
with col_a:
    fig = px.bar(state_agg, x="상태", y="건수", color="상태",
                 labels={"건수": "건수"}, title="상태별 건수")
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0),
                      plot_bgcolor="white", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
with col_b:
    fig = px.bar(state_agg, x="상태", y="매출", color="상태",
                 labels={"매출": "매출 (원)"}, title="상태별 매출")
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0),
                      plot_bgcolor="white", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# ============== 서비스별 매출 ==============
st.markdown("## 💎 서비스별 매출 (확정 건)")

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
        labels={"매출": "매출 (원)"},
        color_discrete_sequence=[PRIMARY],
        text="매출",
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(
        height=max(360, 28 * len(svc_agg)),
        margin=dict(l=0, r=80, t=20, b=0),
        plot_bgcolor="white",
        yaxis=dict(title=""),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("확정 매출 데이터 없음.")

# ============== 신규 vs 갱신 vs 일회성 ==============
st.markdown("## 🆕 신규 vs 갱신 vs 일회성")

nr_agg = (
    confirmed.groupby("신규갱신")
    .agg(건수=("name", "count"), 매출=("총매출", "sum"))
    .reset_index()
)
if not nr_agg.empty:
    nr_agg["평균단가"] = (nr_agg["매출"] / nr_agg["건수"]).round(0)

    col_x, col_y = st.columns(2)
    with col_x:
        fig = px.pie(nr_agg, values="매출", names="신규갱신", hole=0.45,
                     color_discrete_sequence=[PRIMARY, ACCENT, WARN])
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0),
                          title="매출 비중", title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)
    with col_y:
        nr_view = nr_agg.copy()
        nr_view["매출"] = nr_view["매출"].apply(lambda v: f"{v:,.0f}원")
        nr_view["평균단가"] = nr_view["평균단가"].apply(lambda v: f"{v:,.0f}원")
        st.dataframe(nr_view, hide_index=True, use_container_width=True)

    # 갱신 단가 vs 신규 단가 비교 인사이트
    nr_pivot = nr_agg.set_index("신규갱신")
    if "신규" in nr_pivot.index and "갱신" in nr_pivot.index:
        new_unit = nr_pivot.loc["신규", "매출"] / nr_pivot.loc["신규", "건수"]
        ren_unit = nr_pivot.loc["갱신", "매출"] / nr_pivot.loc["갱신", "건수"]
        if new_unit > 0:
            ratio = ren_unit / new_unit
            if ratio < 0.5:
                st.markdown(
                    f'<div class="alert-box">⚠️ 갱신 평균 단가가 신규의 '
                    f'<b>{ratio*100:.0f}%</b>에 불과 — 갱신 시 다운셀·할인 관행 검토 필요.</div>',
                    unsafe_allow_html=True,
                )

# ============== 정산유형별 ==============
st.markdown("## 💳 정산유형별 분포")

st_agg = (
    confirmed.groupby("정산유형", dropna=False)
    .agg(건수=("name", "count"), 매출=("총매출", "sum"))
    .reset_index()
    .fillna("(미입력)")
)
st_view = st_agg.copy()
st_view["매출"] = st_view["매출"].apply(lambda v: f"{v:,.0f}원")
st.dataframe(st_view.sort_values("건수", ascending=False), hide_index=True, use_container_width=True)

# 미입력 경고
not_filled = st_agg[st_agg["정산유형"] == "(미입력)"]
if not not_filled.empty and not_filled.iloc[0]["건수"] > 0:
    st.markdown(
        f'<div class="alert-box">⚠️ 정산유형 미입력 '
        f'<b>{not_filled.iloc[0]["건수"]}건</b> ({not_filled.iloc[0]["매출"]/1e8:.2f}억) — DB 정합성 점검 필요.</div>',
        unsafe_allow_html=True,
    )

# ============== 계약 → 발행 지연 ==============
st.markdown("## ⏱️ 계약 → 세금계산서 발행 지연")

issued = fdf[(fdf["계약일"].notna()) & (fdf["세금계산서발행일"].notna())].copy()
issued["지연일"] = (issued["세금계산서발행일"] - issued["계약일"]).dt.days
if not issued.empty:
    col_p, col_q = st.columns([1, 2])
    with col_p:
        st.metric("평균 지연일", f"{issued['지연일'].mean():.1f}일")
        st.metric("최소 / 최대", f"{issued['지연일'].min()}일 / {issued['지연일'].max()}일")
        st.caption(f"대상: {len(issued)}건")
    with col_q:
        fig = px.histogram(issued, x="지연일", nbins=20,
                           color_discrete_sequence=[PRIMARY],
                           labels={"지연일": "계약→발행 일수"})
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0),
                          plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("계약일·발행일 모두 채워진 건이 없음.")

# ============== 계약 관리 (성공·입금완료·정산완료) ==============
st.markdown("## 💼 계약 관리 — 성사 건 (성공 · 입금완료 · 정산완료)")
st.caption("계약 타입 분류: `신규/갱신` + `정산유형` 조합 기준. 미입력 건은 정산유형 채워야 정확히 분류됩니다.")

confirmed_mgmt = fdf[fdf["상태"].isin(confirmed_states)].copy()
confirmed_mgmt["계약타입"] = confirmed_mgmt.apply(classify_contract, axis=1)

# 타입별 KPI
type_agg = (
    confirmed_mgmt.groupby("계약타입")
    .agg(건수=("name", "count"), 매출=("총매출", "sum"))
    .reset_index()
)
type_agg["계약타입"] = pd.Categorical(
    type_agg["계약타입"], categories=CONTRACT_TYPE_ORDER, ordered=True
)
type_agg = type_agg.sort_values("계약타입").dropna(subset=["계약타입"])

if not type_agg.empty:
    cols = st.columns(len(type_agg))
    for col, (_, row) in zip(cols, type_agg.iterrows()):
        emoji = CONTRACT_TYPE_EMOJI.get(row["계약타입"], "")
        col.markdown(
            f'<div class="kpi-box"><div class="kpi-label">{emoji} {row["계약타입"]}</div>'
            f'<div class="kpi-value">{row["건수"]}건</div>'
            f'<div class="kpi-sub">{row["매출"]/1e8:.2f}억</div></div>',
            unsafe_allow_html=True,
        )

# 타입별 상세표 (확장 가능)
st.markdown("### 📋 계약 타입별 상세")

for ct in CONTRACT_TYPE_ORDER:
    rows = confirmed_mgmt[confirmed_mgmt["계약타입"] == ct]
    if rows.empty:
        continue
    emoji = CONTRACT_TYPE_EMOJI.get(ct, "")
    total_rev = rows["총매출"].sum()
    paid_count = rows["입금완료"].sum()
    expand = ct in ("구독 (월납)", "구독 (분납)", "구독 (정산유형 미입력)")
    with st.expander(
        f"{emoji} **{ct}** — {len(rows)}건 · {total_rev/1e8:.2f}억 · 입금완료 체크 {paid_count}/{len(rows)}",
        expanded=expand,
    ):
        view = rows[[
            "고객기관", "name", "서비스명", "총매출",
            "계약일", "세금계산서발행일", "입금완료", "상태", "url",
        ]].copy()
        view.columns = ["고객기관", "건명", "서비스", "금액",
                        "계약일", "발행일", "입금완료", "상태", "Notion"]

        # 표시용 포맷
        view["금액"] = view["금액"].apply(lambda v: f"{v:,.0f}원")
        view["서비스"] = view["서비스"].apply(lambda lst: ", ".join(lst) if lst else "")
        view["계약일"] = view["계약일"].dt.strftime("%Y-%m-%d").fillna("-")
        view["발행일"] = view["발행일"].dt.strftime("%Y-%m-%d").fillna("-")
        view["입금완료"] = view["입금완료"].apply(lambda b: "✅" if b else "⬜")

        # 월납 계약은 다음 청구 예상월 추가
        if ct == "구독 (월납)":
            next_months = []
            for _, r in rows.iterrows():
                base = r["세금계산서발행일"] if pd.notna(r["세금계산서발행일"]) else r["계약일"]
                if pd.notna(base):
                    nxt = base + pd.DateOffset(months=1)
                    next_months.append(nxt.strftime("%Y-%m"))
                else:
                    next_months.append("-")
            view.insert(6, "다음 청구 예상", next_months)

        st.dataframe(
            view,
            column_config={
                "Notion": st.column_config.LinkColumn("Notion", display_text="열기"),
            },
            hide_index=True,
            use_container_width=True,
        )

        # 타입별 가이드 메모
        if ct == "구독 (월납)":
            st.caption(
                "ℹ️ 월납은 매월 세금계산서 발행 필요. 현재 DB는 계약 단위 1행이라 "
                "월별 발행 이력 추적이 어렵습니다. 정확한 관리를 위해 `매월 발행 회차` 컬럼 추가 권장."
            )
        elif ct == "구독 (분납)":
            st.caption(
                "ℹ️ 분납은 2회 또는 3회 분할. 현재 DB는 `분납 회차` `다음 분납일` 컬럼이 "
                "없어 진행 상황 추적이 어렵습니다. 컬럼 추가 권장."
            )
        elif ct == "구독 (정산유형 미입력)":
            st.warning(
                "정산유형이 미입력된 구독 계약. 1회 선납·월납·분납 중 어느 것인지 "
                "Notion에서 입력해주세요."
            )

# 데이터 품질 + 스키마 개선 제안
with st.expander("🛠️ Notion DB 스키마 개선 제안 (월납·분납 관리용)", expanded=False):
    st.markdown("""
**현재 한계**: DB는 계약 단위 1행이라 월납(12회 발행)·분납(2~3회) 회차별 추적 불가.

**권장 컬럼 추가** (영업현황 DB):

| 컬럼명 | 타입 | 용도 |
|---|---|---|
| `분납 회차 (예정)` | Number | 분할정산일 경우 총 회차 (2 또는 3) |
| `분납 진행` | Number | 현재까지 발행·입금된 회차 |
| `다음 청구 예정일` | Date | 다음 세금계산서 발행 예정일 |
| `구독 시작일` | Date | 연간 구독 시작일 (계약일과 다를 수 있음) |
| `구독 종료일` | Date | 연간 구독 종료일 |
| `결제 이력 메모` | Text | "1회: 2026-04-16 / 2회: 2026-07-16 예정" 형식 |

**더 정확한 관리를 원하면**: 결제 이력 전용 sub-DB 분리. 계약 1건 → 결제 N건 relation.
이 경우 별도 DB 설계가 필요해서 1~2시간 작업.
""")

# ============== 종합 인사이트 ==============
st.markdown("## 🔍 종합 인사이트")
insights = []

if not unpaid.empty:
    top_pct = unpaid["총매출"].max() / unpaid["총매출"].sum() * 100
    if top_pct > 50:
        top_name = unpaid.loc[unpaid["총매출"].idxmax(), "고객기관"] or unpaid.loc[unpaid["총매출"].idxmax(), "name"]
        insights.append(f"단일 고객 집중도: **{top_name}** 1건이 미수금의 {top_pct:.0f}% — 회수 우선.")

if not nr_agg.empty:
    new_row = nr_agg[nr_agg["신규갱신"] == "신규"]
    if not new_row.empty:
        total_conf = confirmed["총매출"].sum()
        if total_conf > 0:
            new_pct = new_row["매출"].iloc[0] / total_conf * 100
            if new_pct > 60:
                insights.append(f"신규 매출 의존도: {new_pct:.0f}% — 갱신 매출 비중 확대 전략 검토.")

if not issued.empty and issued["지연일"].std() > 20:
    insights.append(
        f"계약→발행 지연 변동성 큼 (표준편차 {issued['지연일'].std():.0f}일) — "
        f"선/후 발행 정책 정립 필요."
    )

if not not_filled.empty and not_filled.iloc[0]["건수"] > 0:
    insights.append(
        f"정산유형 미입력 {not_filled.iloc[0]['건수']}건 ({not_filled.iloc[0]['매출']/1e8:.2f}억) — "
        f"DB 데이터 정합성 점검."
    )

if insights:
    for ins in insights:
        st.markdown(f"- {ins}")
else:
    st.success("주요 경보 없음. 데이터 양호.")

# ============== 푸터 ==============
st.markdown("---")
st.caption(
    f"마지막 조회: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
    f"출처: Notion 2026 영업현황 DB ({DATA_SOURCE_ID := '2ab3a733...'})"
)
