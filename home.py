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

# ============== 사이드바 (캐시 새로고침만 유지) ==============
st.sidebar.caption(f"전체 {len(df)}건 / 캐시 10분")
if st.sidebar.button("🔄 캐시 새로고침"):
    st.cache_data.clear()
    st.rerun()

# 필터 사이드바 제거 — 전체 데이터를 그대로 사용
fdf = df.copy()
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
        options=["연도별", "분기별", "월별", "일별"],
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
    "연도별": {"freq": "Y",  "fmt": "%Y"},
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
    # 활성 계약의 payment row만 대상 — 단가는 payment row 자체에 저장
    active_pay = payments_df[payments_df["contract_id"].isin(contracts_for_unit["contract_id"])]
    billed = active_pay[active_pay["발행일"].notna()].copy()
    # 대납액은 매출이 아니므로 제외 (회사가 선납 후 고객에게 환수받는 pass-through)
    billed = billed[billed["결제방법"].astype(str).str.strip() != "대납액"]
    billed["단가"] = pd.to_numeric(billed["단가"], errors="coerce").fillna(0)
else:
    billed = pd.DataFrame()

if billed.empty:
    st.info(
        "기간 내 세금계산서 발행 회차가 없습니다. "
        "계약 관리에서 회차별 발행일을 입력하면 여기에 반영됩니다."
    )
else:
    # 연도별 비교가 가능한 그룹 막대 — 월별/분기별일 때 연도별 색 분리
    billed["년도"] = billed["발행일"].dt.year.astype(str)

    # 색상은 그 해의 천간(天干) 오행에 따라 매핑.
    # 갑·을=木(청록), 병·정=火(적), 무·기=土(황), 경·신=金(은회), 임·계=水(검정)
    # 예: 2024 갑진(청룡)=청, 2025 을사(푸른뱀)=청록, 2026 병오(붉은말)=적
    _CHEONGAN_COLOR = {
        0: "#1E88E5",  # 갑(甲) 木 — 청
        1: "#26A69A",  # 을(乙) 木 — 청록
        2: "#E53935",  # 병(丙) 火 — 적
        3: "#FB8C00",  # 정(丁) 火 — 주홍
        4: "#FDD835",  # 무(戊) 土 — 황금
        5: "#FFB300",  # 기(己) 土 — 황
        6: "#B0BEC5",  # 경(庚) 金 — 은회
        7: "#90A4AE",  # 신(辛) 金 — 회
        8: "#37474F",  # 임(壬) 水 — 짙은 회청
        9: "#1C1C1C",  # 계(癸) 水 — 검정
    }
    _years = sorted(billed["년도"].unique())
    _color_map = {y: _CHEONGAN_COLOR[(int(y) - 4) % 10] for y in _years}

    # 범례·trace 순서를 연도 오름차순으로 고정 (2023 → 2024 → 2025 → 2026)
    _cat_orders = {"년도": _years}

    if period_unit == "월별":
        billed["월"] = billed["발행일"].dt.month
        agg = billed.groupby(["월", "년도"])["단가"].sum().reset_index()
        agg["period_label"] = agg["월"].astype(str) + "월"
        fig = px.bar(
            agg, x="월", y="단가", color="년도",
            color_discrete_map=_color_map, barmode="group",
            category_orders=_cat_orders,
            labels={"단가": "", "월": "", "년도": ""},
            custom_data=["년도", "period_label"],
        )
        fig.update_xaxes(
            tickmode="array", tickvals=list(range(1, 13)),
            ticktext=[f"{m}월" for m in range(1, 13)],
        )
    elif period_unit == "분기별":
        billed["분기"] = billed["발행일"].dt.quarter
        agg = billed.groupby(["분기", "년도"])["단가"].sum().reset_index()
        agg["period_label"] = "Q" + agg["분기"].astype(str)
        fig = px.bar(
            agg, x="분기", y="단가", color="년도",
            color_discrete_map=_color_map, barmode="group",
            category_orders=_cat_orders,
            labels={"단가": "", "분기": "", "년도": ""},
            custom_data=["년도", "period_label"],
        )
        fig.update_xaxes(
            tickmode="array", tickvals=[1, 2, 3, 4],
            ticktext=["Q1", "Q2", "Q3", "Q4"],
        )
    elif period_unit == "연도별":
        agg = billed.groupby("년도")["단가"].sum().reset_index()
        agg["period_label"] = agg["년도"]
        fig = px.bar(
            agg, x="년도", y="단가",
            color="년도", color_discrete_map=_color_map,
            category_orders=_cat_orders,
            labels={"단가": "", "년도": ""},
            custom_data=["년도", "period_label"],
        )
        # x축에 연도(category)만 표기 — 추가 축선·tick 마크 없이
        fig.update_xaxes(type="category")
    else:  # 일별
        billed["일"] = billed["발행일"].dt.date
        agg = billed.groupby("일")["단가"].sum().reset_index()
        agg["period_label"] = agg["일"].astype(str)
        fig = px.bar(
            agg, x="일", y="단가",
            color_discrete_sequence=["#A78BFA"],
            labels={"단가": "", "일": ""},
            custom_data=["period_label"],
        )

    # 호버 — 연도 + 기간 라벨 같이 표시
    if period_unit == "일별":
        _hover = "<b>%{customdata[0]}</b><br>%{y:,.0f}원<extra></extra>"
    else:
        _hover = "<b>%{customdata[0]}년 %{customdata[1]}</b><br>%{y:,.0f}원<extra></extra>"

    fig.update_traces(
        marker=dict(line=dict(width=0), opacity=0.92),
        hovertemplate=_hover,
    )
    fig.update_layout(
        height=380,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=20, r=20, t=50, b=20),
        font=dict(family="Pretendard, Malgun Gothic, 맑은 고딕, sans-serif",
                  size=12, color="#374151"),
        showlegend=(period_unit in ("월별", "분기별", "연도별")),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            x=0, xanchor="left",
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color="#6B6A73"),
            itemclick="toggle", itemwidth=30,
        ),
        xaxis=dict(
            showline=False, showgrid=False, zeroline=False,
            tickfont=dict(size=11, color="#6B6A73"),
            ticks="", title="",
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#F4F2FA", gridwidth=1,
            showline=False, zeroline=False, title="",
            separatethousands=True,
            tickfont=dict(size=10, color="#9CA3AF"),
            ticksuffix="  ",
        ),
        bargap=0.35, bargroupgap=0.12,
        hoverlabel=dict(
            bgcolor="rgba(31, 30, 41, 0.92)", bordercolor="rgba(0,0,0,0)",
            font=dict(family="Pretendard, sans-serif", size=12, color="white"),
            align="left",
        ),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    total_issued = agg["단가"].sum()
    st.caption(f"누적 발행 매출: **{total_issued:,.0f}원** · {total_issued/1e8:.2f}억")

    # ----- 자동 분석 — 분기별/월별은 YoY 동일 기간 비교 중심 -----
    _year_totals = billed.groupby("년도")["단가"].sum().sort_index()
    _analysis_lines = []

    def _yoy_pivot(period_col, period_label_fn):
        """동일 기간(분기/월)별로 연도를 columns로 펼친 pivot 반환."""
        return billed.groupby([period_col, "년도"])["단가"].sum().unstack()

    def _fmt_amt(v):
        """금액을 보기 좋게 (1억 이상은 억, 그 외는 백만)."""
        if v >= 1e8:
            return f"{v/1e8:.2f}억"
        return f"{v/1e6:.1f}백만"

    if period_unit == "분기별" and "분기" in billed.columns and len(_year_totals) >= 2:
        # 분기별 YoY 비교 (직전 연도 vs 최신 연도)
        _piv = _yoy_pivot("분기", lambda q: f"Q{q}")
        _latest_y = _piv.columns[-1]
        _prev_y = _piv.columns[-2]
        _yoy = _piv[[_prev_y, _latest_y]].copy()

        # 최신 연도가 올해면 현재 분기까지만 비교 (미래 분기 제외)
        _today_ts = pd.Timestamp.today()
        if str(_latest_y) == str(_today_ts.year):
            _curr_q = _today_ts.quarter
            _yoy = _yoy[_yoy.index <= _curr_q]

        _analysis_lines.append(
            f"📊 **{_prev_y}년 vs {_latest_y}년 분기 비교** "
            f"(동일 분기 매출 변화 · 현재 분기까지)"
        )

        _quarter_lines = []
        _best = (None, -1e18)
        _worst = (None, 1e18)
        for _q in sorted(_yoy.index):
            _p = _yoy.loc[_q, _prev_y]
            _c = _yoy.loc[_q, _latest_y]
            if pd.isna(_p) and pd.isna(_c):
                continue
            _p = 0 if pd.isna(_p) else _p
            _c = 0 if pd.isna(_c) else _c
            if _p > 0 and _c > 0:
                _pct = (_c - _p) / _p * 100
                _icon = "📈" if _pct >= 0 else "📉"
                _quarter_lines.append(
                    f"&nbsp;&nbsp;{_icon} **Q{_q}**: {_fmt_amt(_p)} → {_fmt_amt(_c)} "
                    f"(**{_pct:+.1f}%**)"
                )
                if _pct > _best[1]:
                    _best = (_q, _pct)
                if _pct < _worst[1]:
                    _worst = (_q, _pct)
            elif _p == 0 and _c > 0:
                _quarter_lines.append(
                    f"&nbsp;&nbsp;✨ **Q{_q}**: {_prev_y}년 매출 없음 → "
                    f"{_latest_y}년 {_fmt_amt(_c)} 신규 매출"
                )
            elif _p > 0 and _c == 0:
                _quarter_lines.append(
                    f"&nbsp;&nbsp;⚠️ **Q{_q}**: {_prev_y}년 {_fmt_amt(_p)} → "
                    f"{_latest_y}년 0원 (미발생/예정)"
                )
        _analysis_lines.extend(_quarter_lines)

        # 좋은 점 / 유의점
        if _best[0] is not None and _best[1] > 10:
            _analysis_lines.append(
                f"✅ **좋은 점**: Q{_best[0]} 매출이 전년 대비 **{_best[1]:+.1f}%** 성장 — "
                f"강세 분기"
            )
        if _worst[0] is not None and _worst[1] < -10:
            _analysis_lines.append(
                f"⚠️ **유의점**: Q{_worst[0]} 매출이 전년 대비 **{_worst[1]:+.1f}%** 감소 — "
                f"원인 점검·영업 강화 필요"
            )

    elif period_unit == "월별" and "월" in billed.columns and len(_year_totals) >= 2:
        # 월별 YoY 비교 (직전 연도 vs 최신 연도)
        _piv = _yoy_pivot("월", lambda m: f"{m}월")
        _latest_y = _piv.columns[-1]
        _prev_y = _piv.columns[-2]
        _yoy = _piv[[_prev_y, _latest_y]].copy()

        # 최신 연도가 올해면 현재 월까지만 비교 (미래 월 제외)
        _today_ts = pd.Timestamp.today()
        if str(_latest_y) == str(_today_ts.year):
            _curr_m = _today_ts.month
            _yoy = _yoy[_yoy.index <= _curr_m]

        _analysis_lines.append(
            f"📊 **{_prev_y}년 vs {_latest_y}년 월 비교** "
            f"(동일 월 매출 변화 · 현재 월까지)"
        )

        _changes = []
        for _m in sorted(_yoy.index):
            _p = _yoy.loc[_m, _prev_y]
            _c = _yoy.loc[_m, _latest_y]
            _p = 0 if pd.isna(_p) else _p
            _c = 0 if pd.isna(_c) else _c
            if _p > 0 and _c > 0:
                _pct = (_c - _p) / _p * 100
                _changes.append((_m, _p, _c, _pct))

        # 성장 상위 3 + 감소 하위 3 추출
        _grew = sorted(_changes, key=lambda x: x[3], reverse=True)[:3]
        _shrank = sorted([x for x in _changes if x[3] < 0], key=lambda x: x[3])[:3]

        if _grew:
            _g_parts = [f"**{m}월** ({pct:+.0f}%)" for m, _, _, pct in _grew]
            _analysis_lines.append(
                f"&nbsp;&nbsp;📈 성장 상위: " + ", ".join(_g_parts)
            )
        if _shrank:
            _s_parts = [f"**{m}월** ({pct:+.0f}%)" for m, _, _, pct in _shrank]
            _analysis_lines.append(
                f"&nbsp;&nbsp;📉 감소 상위: " + ", ".join(_s_parts)
            )

        # 좋은 점 / 유의점
        if _grew and _grew[0][3] > 10:
            _b_m, _b_p, _b_c, _b_pct = _grew[0]
            _analysis_lines.append(
                f"✅ **좋은 점**: {_b_m}월 매출 전년 동월 대비 **{_b_pct:+.0f}%** "
                f"({_fmt_amt(_b_p)} → {_fmt_amt(_b_c)}) — 강세 월"
            )
        if _shrank and _shrank[0][3] < -10:
            _w_m, _w_p, _w_c, _w_pct = _shrank[0]
            _analysis_lines.append(
                f"⚠️ **유의점**: {_w_m}월 매출 전년 동월 대비 **{_w_pct:+.0f}%** "
                f"({_fmt_amt(_w_p)} → {_fmt_amt(_w_c)}) — 점검 필요"
            )

    else:
        # 연도별·일별 또는 연도가 1개뿐인 경우 — 기본 요약
        if len(_year_totals) >= 2:
            _latest_year = _year_totals.index[-1]
            _prev_year = _year_totals.index[-2]
            _latest = _year_totals.iloc[-1]
            _prev = _year_totals.iloc[-2]
            if _prev > 0:
                _growth = (_latest - _prev) / _prev * 100
                _trend_icon = "📈" if _growth >= 0 else "📉"
                _analysis_lines.append(
                    f"{_trend_icon} **{_latest_year}년 매출 {_fmt_amt(_latest)}** — "
                    f"전년({_prev_year}년) 대비 **{_growth:+.1f}%**"
                )
        elif len(_year_totals) == 1:
            _yr = _year_totals.index[0]
            _analysis_lines.append(
                f"📊 **{_yr}년 매출 {_fmt_amt(_year_totals.iloc[0])}** · 단일 연도 데이터"
            )

    # 누적 + 평균 (모든 단위 공통)
    if len(agg) > 0 and total_issued > 0:
        _avg_period = total_issued / len(agg)
        _analysis_lines.append(
            f"💡 누적 매출 **{_fmt_amt(total_issued)}** · "
            f"{period_unit} 평균 **{_fmt_amt(_avg_period)}** "
            f"({len(agg)}개 기간)"
        )

    if _analysis_lines:
        st.markdown(
            "<div style='background:#FAFAFC;border:1px solid #EDECF1;border-radius:8px;"
            "padding:14px 18px;margin-top:10px;font-size:0.88rem;color:#374151;line-height:1.8'>"
            + "<br>".join(_analysis_lines)
            + "</div>",
            unsafe_allow_html=True,
        )

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

# groupby 후 fillna하면 pandas 내부 dtype assertion이 터질 수 있어 사전에 채움
_confirmed_st = confirmed.copy()
_confirmed_st["정산유형"] = _confirmed_st["정산유형"].fillna("(미입력)").astype(str)
st_agg = (
    _confirmed_st.groupby("정산유형")
    .agg(건수=("name", "count"), 매출=("총매출", "sum"))
    .reset_index()
)
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
