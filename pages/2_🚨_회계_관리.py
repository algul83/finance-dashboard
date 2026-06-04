"""원스글로벌 회계 관리 — 미수금 · 세금계산서 발행 누락.

데이터 소스: Google Sheets (계약 관리 페이지와 동일)
계약 관리에서 회차 수정 시 contracts.invalidate_cache()가 호출되어
이 페이지에서도 즉시 최신 값이 반영됨.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import contracts as ct

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
    f'미수금 · 발행 누락 · 계약 관리와 실시간 연동'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ============== 데이터 로드 (계약 관리와 동일 소스) ==============
try:
    contracts_df = ct.load_contracts()
    payments_df = ct.load_payments()
except Exception as e:
    st.error(f"Google Sheets 데이터 로드 실패: {e}")
    st.stop()

if contracts_df.empty:
    st.warning(
        "📭 계약 데이터가 없습니다. 좌측 사이드바 **계약 관리** 메뉴에서 "
        "노션 영업현황을 동기화하세요."
    )
    st.stop()

# 결제 회차 + 계약 메타 조인 (per-payment 뷰)
if not payments_df.empty:
    pay = payments_df.merge(
        contracts_df[["contract_id", "고객기관", "건명", "계약일", "분납회차"]],
        on="contract_id",
        how="left",
    )
else:
    pay = pd.DataFrame(
        columns=list(payments_df.columns) + ["고객기관", "건명", "계약일", "분납회차"]
    )

# ============== 사이드바 ==============
st.sidebar.header("🔧 검색")
search_query = st.sidebar.text_input(
    "고객명 / 건명 키워드",
    value="",
    placeholder="예: 박**병원, ConnectCare",
    help="고객기관·건명에서 부분 일치 검색 (대소문자 무시)",
).strip()

st.sidebar.divider()
st.sidebar.caption(
    f"계약 {len(contracts_df)}건 · 결제 회차 {len(payments_df)}건 / 캐시 60초"
)
if st.sidebar.button("🔄 캐시 새로고침"):
    ct.invalidate_cache()
    st.rerun()


def _apply_search(d: pd.DataFrame) -> pd.DataFrame:
    if not search_query or d.empty:
        return d
    q = search_query.lower()

    def _hit(row):
        for col in ("고객기관", "건명"):
            v = row.get(col, "")
            if v and q in str(v).lower():
                return True
        return False

    return d[d.apply(_hit, axis=1)]


# ============== 집계 ==============
_today = pd.Timestamp.today().normalize()

# 미수금: 세금계산서 발행 O / 입금 X
if not pay.empty:
    unpaid_all = pay[(pay["발행일"].notna()) & (~pay["입금완료"])].copy()
    if not unpaid_all.empty:
        unpaid_all["미수잔액"] = (
            unpaid_all["금액"] - unpaid_all["고객입금액"].fillna(0)
        ).clip(lower=0)
        unpaid_all["경과일"] = (_today - unpaid_all["발행일"]).dt.days
else:
    unpaid_all = pd.DataFrame()

# 발행 누락: 청구예정일 ≤ 오늘 / 발행일 미입력
if not pay.empty:
    overdue_all = pay[
        pay["청구예정일"].notna()
        & (pay["청구예정일"] <= _today)
        & (pay["발행일"].isna())
    ].copy()
    if not overdue_all.empty:
        overdue_all["경과일"] = (_today - overdue_all["청구예정일"]).dt.days
else:
    overdue_all = pd.DataFrame()

unpaid = _apply_search(unpaid_all)
overdue_issue = _apply_search(overdue_all)

# ============== KPI ==============
total_unpaid = float(unpaid["미수잔액"].sum()) if not unpaid.empty else 0.0
total_overdue = float(overdue_issue["금액"].sum()) if not overdue_issue.empty else 0.0
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
        f"{len(unpaid)}회차 · 발행 완료 / 입금 X",
        danger=True,
    ),
    unsafe_allow_html=True,
)
c2.markdown(
    kpi_card(
        "발행 누락",
        f"{total_overdue/1e8:.2f}억",
        f"{len(overdue_issue)}회차 · 청구예정일 경과 / 발행일 미입력",
        warn=True,
    ),
    unsafe_allow_html=True,
)
c3.markdown(
    kpi_card(
        "회수 리스크 합계",
        f"{total_risk/1e8:.2f}억",
        f"{len(unpaid)+len(overdue_issue)}회차 · 미수금 + 발행 누락",
    ),
    unsafe_allow_html=True,
)

# ============== 미수금 상세 ==============
st.markdown("## 🚨 미수금 상세")
st.markdown(
    '<div class="sec-meta">세금계산서 발행 완료 · 입금 미완료 — 경과일 내림차순 · 결제 회차 단위</div>',
    unsafe_allow_html=True,
)

if unpaid_all.empty:
    st.success("미수금 없음. ✅")
elif unpaid.empty:
    st.info(f"'{search_query}' 검색 결과 없음 (전체 미수금 {len(unpaid_all)}회차).")
else:
    view = unpaid[[
        "발행일", "경과일", "고객기관", "건명", "회차", "금액", "고객입금액", "미수잔액", "메모",
    ]].copy()
    view = view.sort_values("경과일", ascending=False).reset_index(drop=True)
    st.dataframe(
        view,
        column_config={
            "발행일": st.column_config.DateColumn("발행일", format="YYYY-MM-DD"),
            "경과일": st.column_config.NumberColumn("경과일", format="%d일"),
            "고객기관": st.column_config.TextColumn("고객기관"),
            "건명": st.column_config.TextColumn("건명"),
            "회차": st.column_config.TextColumn("회차", width="small"),
            "금액": st.column_config.NumberColumn("발행액 (원)", format="localized"),
            "고객입금액": st.column_config.NumberColumn("입금액 (원)", format="localized"),
            "미수잔액": st.column_config.NumberColumn("미수잔액 (원)", format="localized"),
            "메모": st.column_config.TextColumn("메모"),
        },
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        f"합계 미수잔액 **{unpaid['미수잔액'].sum():,.0f}원** · {len(unpaid)}회차 · "
        f"최장 경과 {int(unpaid['경과일'].max())}일"
    )
    # 단일 고객 집중도 경고
    by_cust = unpaid.groupby("고객기관", dropna=False)["미수잔액"].sum().sort_values(ascending=False)
    if not by_cust.empty and by_cust.sum() > 0:
        top_pct = by_cust.iloc[0] / by_cust.sum() * 100
        if top_pct > 50:
            name = by_cust.index[0] or "(고객기관 미입력)"
            st.warning(
                f"⚠️ 단일 고객 집중 위험: **{name}** 미수금이 전체의 **{top_pct:.0f}%** — 우선 회수 권장."
            )

# ============== 세금계산서 발행 누락 ==============
st.markdown("## 📝 세금계산서 발행 누락")
st.markdown(
    '<div class="sec-meta">청구예정일 ≤ 오늘 · 발행일 미입력 — 경과일 내림차순</div>',
    unsafe_allow_html=True,
)

if overdue_all.empty:
    st.success("발행 누락 없음. ✅")
elif overdue_issue.empty:
    st.info(f"'{search_query}' 검색 결과 없음 (전체 발행 누락 {len(overdue_all)}회차).")
else:
    view = overdue_issue[[
        "청구예정일", "경과일", "고객기관", "건명", "회차", "금액", "메모",
    ]].copy()
    view = view.sort_values("경과일", ascending=False, na_position="last").reset_index(drop=True)
    st.dataframe(
        view,
        column_config={
            "청구예정일": st.column_config.DateColumn("청구예정일", format="YYYY-MM-DD"),
            "경과일": st.column_config.NumberColumn("경과일", format="%d일", help="today − 청구예정일"),
            "고객기관": st.column_config.TextColumn("고객기관"),
            "건명": st.column_config.TextColumn("건명"),
            "회차": st.column_config.TextColumn("회차", width="small"),
            "금액": st.column_config.NumberColumn("예정 발행액 (원)", format="localized"),
            "메모": st.column_config.TextColumn("메모"),
        },
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        f"합계 **{overdue_issue['금액'].sum():,.0f}원** · {len(overdue_issue)}회차 · "
        f"최장 경과 {int(overdue_issue['경과일'].max())}일"
    )

# ============== 안내 ==============
st.info(
    "💡 **모든 수치는 [계약 관리 페이지](./계약_관리)와 실시간 연동됩니다.** "
    "계약 관리에서 회차 수정 → 자동 캐시 무효화 → 이 페이지 즉시 갱신. "
    "필요 시 좌측 사이드바 **🔄 캐시 새로고침** 버튼으로 강제 리로드."
)

# ============== 푸터 ==============
st.markdown("---")
st.caption(
    f"마지막 조회: {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
    f"출처: Google Sheets (OnesGlobal Contracts)"
)
