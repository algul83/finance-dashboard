"""계약 관리 페이지 — 고객별 계약 + 결제 회차 관리."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import contracts as ct
from data_loader import load_sales_data

# ============== 색상 ==============
PRIMARY = "#5B43C9"
PRIMARY_DARK = "#4A35B0"
PRIMARY_LIGHT = "#F1EEFB"
ACCENT = "#10B981"
WARN = "#F59E0B"
DANGER = "#E84C3D"

st.set_page_config(
    page_title="계약 관리 — 원스글로벌",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 동일 헤더 스타일 (app.py와 일치)
st.markdown(
    f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, *, [class*="css"], button, input, select, textarea {{
        font-family: 'Pretendard', 'Malgun Gothic', '맑은 고딕', -apple-system, sans-serif !important;
    }}
    .stApp {{ background: white; padding-top: 64px; }}
    [data-testid="stAppViewContainer"] {{ background: white !important; }}
    body, html {{ background: white !important; }}
    [data-testid="stHeader"], header[data-testid="stHeader"],
    div[data-testid="stToolbar"] {{
        display: none !important; height: 0 !important;
    }}
    section[data-testid="stSidebar"] {{ top: 64px !important; }}
    .top-header {{
        background: linear-gradient(90deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        padding: 0 32px;
        display: flex; align-items: center; gap: 20px;
        color: white !important;
        position: fixed; top: 0; left: 0;
        width: 100vw; height: 64px; z-index: 999999;
        box-shadow: 0 1px 4px rgba(91,67,201,0.15);
    }}
    .top-header * {{ color: white !important; }}
    .top-logo {{ font-size: 1.2rem; font-weight: 800; }}
    .top-tag {{
        background: rgba(255,255,255,0.2); padding: 4px 10px;
        border-radius: 4px; font-size: 0.7rem; font-weight: 500;
    }}
    [data-testid="stMainBlockContainer"] {{
        max-width: 1280px !important; padding-top: 24px !important;
    }}
    h1, h2, h3, h4 {{ color: #1E1B2E; }}
    h2 {{ margin-top: 32px !important; border-bottom: 2px solid {PRIMARY_LIGHT}; padding-bottom: 8px; }}
    .kpi-box {{
        background: white; border: 1px solid #EDECF1;
        border-radius: 12px; padding: 14px 16px;
    }}
    .kpi-label {{ color: #6B6A73; font-size: 0.8rem; margin-bottom: 4px; }}
    .kpi-value {{ color: {PRIMARY}; font-size: 1.3rem; font-weight: 800; }}
    .contract-card {{
        background: white; border: 1px solid #EDECF1;
        border-radius: 12px; padding: 16px; margin: 12px 0;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="top-header">'
    f'<div class="top-logo">💼 계약 관리</div>'
    f'<div class="top-tag">Onesglobal Internal</div>'
    f'<div style="flex:1;"></div>'
    f'<div style="color:rgba(255,255,255,0.85);font-size:0.85rem;">'
    f'고객별 계약 · 결제 회차 추적'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ============== Sync 영역 ==============
st.sidebar.header("🔧 작업")

if st.sidebar.button("🔄 Notion에서 신규 성사 건 가져오기", use_container_width=True):
    with st.spinner("Notion 영업현황 조회 중..."):
        try:
            notion_df = load_sales_data()
            added_c, added_p = ct.sync_from_notion(notion_df)
            st.sidebar.success(f"✅ 신규 계약 {added_c}건, 결제 회차 {added_p}건 추가")
            st.cache_data.clear()
        except Exception as e:
            st.sidebar.error(f"동기화 실패: {e}")

if st.sidebar.button("♻️ 캐시 새로고침", use_container_width=True):
    ct.invalidate_cache()
    st.rerun()

# ============== 데이터 로드 ==============
try:
    contracts_df = ct.load_contracts()
    payments_df = ct.load_payments()
except Exception as e:
    st.error(f"Google Sheets 연결 실패: {e}")
    st.info(
        "**셋업 안내**: Streamlit Cloud Secrets에 `gcp_service_account` 블록과 "
        "`CONTRACTS_SHEET_ID`가 입력돼있어야 합니다. README 참고."
    )
    st.stop()

if contracts_df.empty:
    st.info(
        "👋 아직 등록된 계약이 없습니다. 좌측 사이드바의 "
        "**'Notion에서 신규 성사 건 가져오기'** 버튼을 눌러 동기화하세요."
    )
    st.stop()

# ============== 상단 KPI ==============
total_amount = contracts_df["총금액"].sum()
total_paid = payments_df[payments_df["입금완료"]]["금액"].sum() if not payments_df.empty else 0
total_unpaid = total_amount - total_paid
collection_rate = (total_paid / total_amount * 100) if total_amount > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.markdown(
    f'<div class="kpi-box"><div class="kpi-label">전체 계약</div>'
    f'<div class="kpi-value">{len(contracts_df)}건</div></div>',
    unsafe_allow_html=True,
)
c2.markdown(
    f'<div class="kpi-box"><div class="kpi-label">계약 총금액</div>'
    f'<div class="kpi-value">{total_amount/1e8:.2f}억</div></div>',
    unsafe_allow_html=True,
)
c3.markdown(
    f'<div class="kpi-box"><div class="kpi-label">입금 완료</div>'
    f'<div class="kpi-value" style="color:{ACCENT};">{total_paid/1e8:.2f}억</div></div>',
    unsafe_allow_html=True,
)
c4.markdown(
    f'<div class="kpi-box"><div class="kpi-label">미수금</div>'
    f'<div class="kpi-value" style="color:{DANGER};">{total_unpaid/1e8:.2f}억</div>'
    f'<div style="font-size:0.75rem;color:#999;">회수율 {collection_rate:.1f}%</div></div>',
    unsafe_allow_html=True,
)

# ============== 고객 선택 ==============
st.markdown("## 🔍 고객별 계약 조회")
customers = sorted([c for c in contracts_df["고객기관"].unique() if c])
selected_customer = st.selectbox(
    "고객 선택",
    options=["(전체)"] + customers,
    index=0,
)

if selected_customer != "(전체)":
    customer_contracts = contracts_df[contracts_df["고객기관"] == selected_customer]
else:
    customer_contracts = contracts_df

# 고객별 요약 (선택 시)
if selected_customer != "(전체)":
    cust_total = customer_contracts["총금액"].sum()
    cust_paid = (
        payments_df[
            (payments_df["contract_id"].isin(customer_contracts["contract_id"]))
            & (payments_df["입금완료"])
        ]["금액"].sum()
        if not payments_df.empty else 0
    )
    cust_unpaid = cust_total - cust_paid
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric(f"{selected_customer} 계약", f"{len(customer_contracts)}건")
    cc2.metric("총 계약금", f"{cust_total:,.0f}원")
    cc3.metric("미수금", f"{cust_unpaid:,.0f}원", delta=f"-{cust_unpaid/cust_total*100:.0f}%" if cust_total else "0%")

st.markdown(f"### 📋 계약 목록 ({len(customer_contracts)}건)")

# ============== 계약 카드 렌더링 ==============
for _, c in customer_contracts.iterrows():
    contract_id = c["contract_id"]
    contract_payments = payments_df[payments_df["contract_id"] == contract_id] if not payments_df.empty else pd.DataFrame()
    paid_amount = contract_payments[contract_payments["입금완료"]]["금액"].sum() if not contract_payments.empty else 0
    progress = (paid_amount / c["총금액"] * 100) if c["총금액"] > 0 else 0

    header = (
        f"📄 **{c['건명']}** · {c['고객기관']} · "
        f"{c['총금액']:,.0f}원 · {c['신규갱신']} / {c['정산유형'] or '미입력'} · "
        f"입금 {progress:.0f}%"
    )
    with st.expander(header, expanded=False):
        # 계약 정보
        info_cols = st.columns([2, 2, 2, 2])
        info_cols[0].markdown(f"**계약일**\n{c['계약일'].strftime('%Y-%m-%d') if pd.notna(c['계약일']) else '-'}")
        info_cols[1].markdown(f"**서비스**\n{c['서비스명'] or '-'}")
        info_cols[2].markdown(f"**정산유형**\n{c['정산유형'] or '미입력'}")
        info_cols[3].markdown(f"**분납 회차**\n{int(c['분납회차']) if pd.notna(c['분납회차']) else '-'}회")

        # 입금 진행률 바
        st.progress(min(progress / 100, 1.0), text=f"입금 진행: {paid_amount:,.0f} / {c['총금액']:,.0f}원 ({progress:.0f}%)")

        # 메타데이터 수정
        with st.popover("⚙️ 계약 메타 수정"):
            new_분납 = st.number_input(
                "분납 회차 (분할정산일 때 2 또는 3)",
                min_value=0, max_value=12,
                value=int(c["분납회차"]) if pd.notna(c["분납회차"]) else 0,
                key=f"분납_{contract_id}",
            )
            new_구독시작 = st.date_input(
                "구독 시작일",
                value=c["구독시작일"].date() if pd.notna(c["구독시작일"]) else None,
                key=f"시작_{contract_id}",
            )
            new_구독종료 = st.date_input(
                "구독 종료일",
                value=c["구독종료일"].date() if pd.notna(c["구독종료일"]) else None,
                key=f"종료_{contract_id}",
            )
            new_메모 = st.text_area("메모", value=c.get("메모", "") or "", key=f"memo_{contract_id}")
            if st.button("저장", key=f"save_{contract_id}"):
                ct.update_contract_meta(
                    contract_id,
                    분납회차=new_분납 if new_분납 > 0 else "",
                    구독시작일=new_구독시작,
                    구독종료일=new_구독종료,
                    메모=new_메모,
                )
                st.success("저장 완료")
                st.rerun()

        # 결제 회차
        st.markdown("**💳 결제 회차**")
        if contract_payments.empty:
            st.caption("등록된 결제 회차가 없습니다. 아래에서 추가하세요.")
        else:
            view = contract_payments[[
                "payment_id", "회차", "청구예정일", "발행일", "금액", "입금완료", "입금일", "메모",
            ]].copy()
            view["청구예정일"] = view["청구예정일"].dt.strftime("%Y-%m-%d").fillna("-")
            view["발행일"] = view["발행일"].dt.strftime("%Y-%m-%d").fillna("-")
            view["입금일"] = view["입금일"].dt.strftime("%Y-%m-%d").fillna("-")
            view["금액"] = view["금액"].apply(lambda v: f"{v:,.0f}원")
            view["상태"] = view["입금완료"].apply(lambda b: "✅ 입금완료" if b else "⬜ 미입금")
            display = view.drop(columns=["payment_id", "입금완료"])
            st.dataframe(display, hide_index=True, use_container_width=True)

            # 입금 토글
            unpaid = contract_payments[~contract_payments["입금완료"]]
            if not unpaid.empty:
                with st.popover("✅ 입금완료 처리"):
                    for _, p in unpaid.iterrows():
                        label = f"{p['회차']}회차 — {p['금액']:,.0f}원"
                        col_a, col_b = st.columns([3, 2])
                        col_a.write(label)
                        if col_b.button("입금 완료", key=f"paid_{p['payment_id']}"):
                            ct.update_payment_paid(p["payment_id"], True, date.today())
                            st.success(f"{label} 처리됨")
                            st.rerun()

        # 결제 회차 추가
        with st.popover("➕ 결제 회차 추가"):
            with st.form(f"add_payment_{contract_id}"):
                new_회차 = st.text_input("회차 (예: 2, 3, 또는 2026-07)", key=f"new_round_{contract_id}")
                new_청구 = st.date_input("청구 예정일", value=None, key=f"new_due_{contract_id}")
                new_발행 = st.date_input("발행일 (있으면)", value=None, key=f"new_issue_{contract_id}")
                new_금액 = st.number_input("금액 (원)", min_value=0, step=10000, key=f"new_amt_{contract_id}")
                new_메모2 = st.text_input("메모", key=f"new_memo_{contract_id}")
                if st.form_submit_button("회차 추가"):
                    if not new_회차 or not new_금액:
                        st.error("회차와 금액은 필수입니다.")
                    else:
                        ct.add_payment(contract_id, new_회차, new_청구, new_발행, new_금액, new_메모2)
                        st.success(f"{new_회차}회차 추가됨")
                        st.rerun()

        if c.get("메모"):
            st.caption(f"📝 메모: {c['메모']}")

# ============== 푸터 ==============
st.markdown("---")
st.caption(
    f"전체 계약 {len(contracts_df)}건 · 결제 회차 {len(payments_df)}건 · "
    f"캐시 60초 · 출처: Google Sheets (OnesGlobal Contracts)"
)
