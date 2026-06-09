"""원스글로벌 회계 관리 — 미수금 · 세금계산서 발행 누락.

데이터 소스: Google Sheets (계약 관리 페이지와 동일)
계약 관리에서 회차 수정 시 contracts.invalidate_cache()가 호출되어
이 페이지에서도 즉시 최신 값이 반영됨.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st

import card_payments as cp
import contracts as ct
from auth import auth_query_suffix, require_auth

# ============== Palette ==============
PRIMARY = "#5B43C9"
PRIMARY_DARK = "#4A35B0"
PRIMARY_LIGHT = "#F1EEFB"
ACCENT = "#10B981"
WARN = "#F59E0B"
DANGER = "#E84C3D"

# st.set_page_config는 navigation entry(app.py)가 처리. require_auth는 방어용으로 유지.
require_auth()

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
    contracts_df = ct.filter_active_contracts(ct.load_contracts())
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

# 미수금: 세금계산서 발행 후 30일 초과 / 입금 X
if not pay.empty:
    elapsed = (_today - pay["발행일"]).dt.days
    unpaid_all = pay[
        pay["발행일"].notna()
        & (elapsed > 30)
        & (~pay["입금완료"])
    ].copy()
    if not unpaid_all.empty:
        unpaid_all["미수잔액"] = (
            unpaid_all["금액"] - unpaid_all["고객입금액"].fillna(0)
        ).clip(lower=0)
        unpaid_all["경과일"] = (_today - unpaid_all["발행일"]).dt.days
else:
    unpaid_all = pd.DataFrame()

# 발행 누락:
#  (1) 청구예정일 ≤ 오늘 + 발행일 미입력 — 명시적 누락
#  (2) 계약일 ≤ 오늘 + 청구예정일 빈 + 발행일 빈 — 청구예정일조차 안 정한 catch-all
if not pay.empty:
    _missing_dates = pay["청구예정일"].isna() & pay["발행일"].isna()

    cond_explicit = (
        pay["청구예정일"].notna()
        & (pay["청구예정일"] <= _today)
        & pay["발행일"].isna()
    )
    cond_fallback = (
        pay["계약일"].notna()
        & (pay["계약일"] <= _today)
        & _missing_dates
    )

    overdue_all = pay[cond_explicit | cond_fallback].copy()
    if not overdue_all.empty:
        # 기준일: 청구예정일 있으면 그것, 아니면 계약일로 fallback
        _ref_date = overdue_all["청구예정일"].fillna(overdue_all["계약일"])
        overdue_all["기준일"] = _ref_date
        overdue_all["기준"] = overdue_all["청구예정일"].apply(
            lambda x: "청구예정" if pd.notna(x) else "계약일"
        )
        overdue_all["경과일"] = (_today - _ref_date).dt.days
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
        f"{len(unpaid)}회차 · 발행 후 30일 초과 / 입금 X",
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
    '<div class="sec-meta">발행 후 30일 초과 · 입금 미완료 — 경과일 내림차순 · 결제 회차 단위</div>',
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
    '<div class="sec-meta">청구예정일 ≤ 오늘 · 발행일 미입력 (청구예정일이 비어있는 경우 계약일 fallback) — 경과일 내림차순</div>',
    unsafe_allow_html=True,
)

if overdue_all.empty:
    st.success("발행 누락 없음. ✅")
elif overdue_issue.empty:
    st.info(f"'{search_query}' 검색 결과 없음 (전체 발행 누락 {len(overdue_all)}회차).")
else:
    view = overdue_issue[[
        "기준일", "기준", "경과일", "고객기관", "건명", "회차", "금액",
    ]].copy()
    # 건명을 클릭하면 계약 관리 페이지로 이동 + 해당 건명으로 자동 검색
    _auth_q = auth_query_suffix()
    view["계약 상세"] = view["건명"].apply(
        lambda b: f"./계약_관리?q={quote(str(b))}{_auth_q}"
    )
    view = view.sort_values("경과일", ascending=False, na_position="last").reset_index(drop=True)
    st.dataframe(
        view,
        column_config={
            "기준일": st.column_config.DateColumn("기준일", format="YYYY-MM-DD"),
            "기준": st.column_config.TextColumn(
                "기준",
                width="small",
                help="청구예정 = 청구예정일 / 계약일 = 청구예정일 미설정 시 계약일 fallback",
            ),
            "경과일": st.column_config.NumberColumn("경과일", format="%d일", help="today − 기준일"),
            "고객기관": st.column_config.TextColumn("고객기관"),
            "건명": st.column_config.TextColumn("건명"),
            "회차": st.column_config.TextColumn("회차", width="small"),
            "금액": st.column_config.NumberColumn("예정 발행액 (원)", format="localized"),
            "계약 상세": st.column_config.LinkColumn(
                "계약 상세",
                display_text="펼치기 →",
                width="small",
                help="계약 관리 페이지에서 해당 건명으로 자동 검색됩니다",
            ),
        },
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        f"합계 **{overdue_issue['금액'].sum():,.0f}원** · {len(overdue_issue)}회차 · "
        f"최장 경과 {int(overdue_issue['경과일'].max())}일"
    )

# ============== 카드결제 정산 ==============
st.markdown("## 💳 카드결제 정산")
st.markdown(
    '<div class="sec-meta">이노페이/토스 정산내역 엑셀 업로드 → 자동 매칭</div>',
    unsafe_allow_html=True,
)

up_col, pg_col = st.columns([4, 1])
with pg_col:
    pg_sel = st.selectbox("PG", ["이노페이", "토스"], key="card_pg_sel")
with up_col:
    uploaded = st.file_uploader(
        "정산내역 엑셀 업로드 (.xls / .xlsx)",
        type=["xls", "xlsx"],
        key="card_upload",
        help="이노페이는 HTML 위장 .xls 파일도 자동 인식",
    )

if uploaded is not None:
    try:
        if pg_sel == "이노페이":
            parsed = cp.parse_innopay(uploaded)
        else:
            st.info("토스 PG 파서는 다음 단계에서 추가 예정 — 현재는 이노페이만 지원")
            parsed = pd.DataFrame()
    except Exception as e:
        st.error(f"파싱 실패: {type(e).__name__}: {e}")
        parsed = pd.DataFrame()

    if not parsed.empty:
        st.caption(f"파싱 성공: **{len(parsed)}건** (승인 {(parsed['상태']=='승인').sum()}건 / 취소 {(parsed['상태']!='승인').sum()}건)")
        st.dataframe(
            parsed[["결제일", "구매자", "거래금액", "정산금액", "카드사", "상품명", "상태"]],
            hide_index=True,
            use_container_width=True,
        )
        if st.button("📥 시트에 저장 + 자동 매칭", type="primary", key="card_save"):
            with st.spinner("매칭 중..."):
                result = cp.auto_match_and_save(parsed, contracts_df, payments_df)
            st.success(
                f"✅ {result['saved']}건 저장 · 자동매칭 {result['auto']} · "
                f"다중후보 {result['multi']} · 미매칭 {result['miss']} · "
                f"Payments 반영 {result.get('applied', 0)}"
            )
            ct.invalidate_cache()
            st.rerun()

# 저장된 카드결제 — 미매칭/다중후보 우선 표시
try:
    card_df = cp.load_card_payments()
except Exception as e:
    card_df = pd.DataFrame()
    st.warning(f"CardPayments 시트 로드 실패: {str(e)[:120]}")

if not card_df.empty:
    pending = card_df[card_df["매칭_상태"].isin(["미매칭", "다중"])].copy().reset_index(drop=True)
    st.markdown(f"### 🔧 미매칭/다중 후보 ({len(pending)}건)")
    if pending.empty:
        st.success("모든 카드결제가 자동 매칭 완료. ✅")
    else:
        # ----- 1) 체크박스 선택 + 일괄 신규 계약 생성 -----
        st.markdown("##### 🆕 신규 계약 일괄 생성 (노션 미관리 건)")
        pending_view = pending[[
            "결제일", "구매자", "거래금액", "카드사", "상품명", "매칭_상태",
        ]].copy()
        pending_view.insert(0, "선택", False)
        edited_pending = st.data_editor(
            pending_view,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", width="small"),
                "결제일": st.column_config.DateColumn("결제일", format="YYYY-MM-DD"),
                "구매자": st.column_config.TextColumn("구매자"),
                "거래금액": st.column_config.NumberColumn("거래금액", format="localized"),
                "카드사": st.column_config.TextColumn("카드사", width="small"),
                "상품명": st.column_config.TextColumn("상품명"),
                "매칭_상태": st.column_config.TextColumn("상태", width="small"),
            },
            disabled=["결제일", "구매자", "거래금액", "카드사", "상품명", "매칭_상태"],
            hide_index=True,
            use_container_width=True,
            key="card_pending_select",
        )
        _sel_idx = edited_pending[edited_pending["선택"]].index.tolist()
        if st.button(
            f"🆕 선택한 {len(_sel_idx)}건을 신규 계약으로 생성",
            type="primary",
            disabled=len(_sel_idx) == 0,
            key="card_bulk_create",
        ):
            ok = 0
            errs = []
            for idx in _sel_idx:
                card = pending.iloc[idx]
                try:
                    new_pid = ct.create_contract_from_card(card)
                    cp.set_match(card["card_id"], new_pid)
                    ok += 1
                except Exception as e:
                    errs.append(f"{card['구매자']}: {type(e).__name__}: {e}")
            ct.invalidate_cache()
            cp.invalidate_cache()
            st.success(f"✅ {ok}건 신규 계약 + 회차 생성 + 매칭 완료")
            for err in errs:
                st.error(err)
            st.rerun()
        st.caption(
            "💡 선택한 카드결제 각각에 대해 새 Contracts + 1회차 Payments row를 만들고 "
            "결제정보(결제일·정산일·금액·결제방법=카드결제·입금완료=TRUE)까지 자동 입력합니다."
        )

        # ----- 2) 1건 선택 시 계약명 검색해서 기존 회차에 매칭 -----
        if len(_sel_idx) == 1:
            _selected_card = pending.iloc[_sel_idx[0]]
            st.markdown("##### 🔎 또는 선택한 1건을 기존 계약 회차에 매칭")
            st.caption(
                f"선택: **{_selected_card['구매자']}** · "
                f"{int(_selected_card['거래금액']):,}원 · "
                f"{(_selected_card['결제일'].strftime('%Y-%m-%d') if pd.notna(_selected_card['결제일']) else '?')}"
            )
            search_q = st.text_input(
                "계약명/고객기관 검색",
                placeholder="예: 양산부산대 / 김홍아 / 충남대",
                key="card_match_search",
                help="결제방법이 미지정(빈 셀)인 회차만 매칭 가능",
            )
            if search_q:
                _cand_base = payments_df.merge(
                    contracts_df[["contract_id", "고객기관", "건명"]],
                    on="contract_id", how="left",
                )
                _cand_base["금액_n"] = pd.to_numeric(
                    _cand_base["금액"], errors="coerce"
                ).fillna(0).astype(int)
                q_low = search_q.strip().lower()
                matches = _cand_base[
                    (_cand_base["결제방법"].astype(str).str.strip() == "")
                    & (
                        _cand_base["고객기관"].astype(str).str.lower().str.contains(q_low, na=False)
                        | _cand_base["건명"].astype(str).str.lower().str.contains(q_low, na=False)
                    )
                ].copy()
                amount = int(_selected_card["거래금액"])
                matches["_amt_match"] = matches["금액_n"] == amount
                matches = matches.sort_values(
                    ["_amt_match", "청구예정일"], ascending=[False, False]
                ).head(50)

                if matches.empty:
                    st.warning(
                        f"'{search_q}' 검색 결과 없음 (결제방법이 미지정인 회차만 매칭 가능). "
                        "계약 관리에서 결제방법을 비우거나 새 회차를 만들어야 합니다."
                    )
                else:
                    options = ["(매칭 안 함)"]
                    opt_pids = [""]
                    for _, r in matches.iterrows():
                        marker = "🎯 " if r["_amt_match"] else "   "
                        label = (
                            f"{marker}{r['고객기관'] or '?'} / {r['건명'] or '?'} / "
                            f"회차 {r['회차']} · {r['금액_n']:,}원"
                        )
                        options.append(label)
                        opt_pids.append(r["payment_id"])
                    sel = st.selectbox(
                        f"매칭할 회차 ({len(matches)}개 결과)",
                        options=options,
                        key="card_search_match_sel",
                        help="🎯 표시는 카드 거래금액과 정확히 일치하는 후보",
                    )
                    if st.button(
                        "✅ 매칭 적용",
                        type="primary",
                        disabled=(sel == "(매칭 안 함)"),
                        key="card_search_match_btn",
                    ):
                        try:
                            cp.set_match(_selected_card["card_id"], opt_pids[options.index(sel)])
                            ct.invalidate_cache()
                            st.success("✅ 매칭 적용 + Payments에 반영됨")
                            st.rerun()
                        except Exception as e:
                            st.error(f"매칭 실패: {type(e).__name__}: {e}")
        elif len(_sel_idx) >= 2:
            st.caption("💡 검색 매칭은 한 번에 1건만 가능 — 1개만 선택하면 검색 입력창이 보입니다.")

    # 자동·수동 매칭된 카드결제 — 매칭된 계약/회차 정보까지 join
    matched = card_df[card_df["매칭_상태"].isin(["자동", "수동"])]
    with st.expander(f"✅ 매칭 완료 카드결제 ({len(matched)}건)", expanded=False):
        if matched.empty:
            st.info("매칭 완료된 카드결제 없음.")
        else:
            _pinfo = payments_df[["payment_id", "contract_id", "회차"]].copy()
            _cinfo = contracts_df[["contract_id", "고객기관", "건명"]].copy()
            joined = (
                matched.merge(
                    _pinfo, left_on="매칭_payment_id", right_on="payment_id", how="left"
                )
                .merge(_cinfo, on="contract_id", how="left")
            )
            view = joined[[
                "결제일", "정산일", "구매자", "거래금액", "정산금액", "카드사",
                "고객기관", "건명", "회차", "매칭_상태", "상품명",
            ]].sort_values("결제일", ascending=False).reset_index(drop=True)
            st.dataframe(
                view,
                column_config={
                    "결제일": st.column_config.DateColumn("결제일", format="YYYY-MM-DD"),
                    "정산일": st.column_config.DateColumn("정산일", format="YYYY-MM-DD"),
                    "거래금액": st.column_config.NumberColumn("거래금액", format="localized"),
                    "정산금액": st.column_config.NumberColumn("정산금액", format="localized"),
                    "회차": st.column_config.TextColumn("회차", width="small"),
                    "매칭_상태": st.column_config.TextColumn("매칭", width="small"),
                },
                hide_index=True,
                use_container_width=True,
            )

    sync_col1, sync_col2 = st.columns([2, 5])
    with sync_col1:
        if st.button("🔁 매칭 전체를 Payments에 재반영", key="card_resync"):
            with st.spinner("Payments 동기화 중..."):
                n = cp.sync_all_matched_to_payments()
            st.success(f"✅ {n}건 Payments 반영 완료")
            ct.invalidate_cache()
            st.rerun()
    with sync_col2:
        st.caption(
            f"누적 카드결제: **{len(card_df)}건** · 매칭 완료 {len(matched)} · "
            f"매칭 거래액 합계 {matched['거래금액'].sum():,.0f}원"
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
