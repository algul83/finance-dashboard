"""계약 관리 페이지 — 고객별 계약 + 결제 회차 관리."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import contracts as ct
from auth import require_auth
from data_loader import load_sales_data, notion_source_status

# ============== 색상 ==============
PRIMARY = "#5B43C9"
PRIMARY_DARK = "#4A35B0"
PRIMARY_LIGHT = "#F1EEFB"
ACCENT = "#10B981"
WARN = "#F59E0B"
DANGER = "#E84C3D"

# st.set_page_config는 navigation entry(app.py)가 처리. require_auth는 방어용으로 유지.
require_auth()

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
    /* 계약 카드 — 모든 컬럼(텍스트 + 버튼)을 한 줄 세로 가운데 정렬 */
    div[data-testid="stVerticalBlockBorderWrapper"]
        div[data-testid="stHorizontalBlock"] {{
        align-items: center !important;
    }}
    /* 펼침/접기 토글 버튼 (▼/▲) 높이 절반 */
    div[data-testid="stVerticalBlockBorderWrapper"]
        div[data-testid="stHorizontalBlock"]
        > div[data-testid="stColumn"]:last-child
        .stButton button {{
        min-height: 26px !important;
        height: 26px !important;
        padding: 0 6px !important;
        line-height: 1 !important;
    }}
    /* 메타 수정 popover wrapper도 buttom과 동일 크기 강제 */
    div[data-testid="stPopover"] {{
        width: 100% !important;
    }}
    div[data-testid="stPopover"] > div,
    div[data-testid="stPopover"] > div > div {{
        width: 100% !important;
        height: 44px !important;
    }}
    /* 메타 수정 popover + 변경사항 저장 버튼 본체 — 동일 크기 강제 */
    .stButton > button[kind="primary"],
    div[data-testid="stPopover"] button,
    button[kind="popover"],
    [data-testid="stPopoverButton"] {{
        height: 44px !important;
        min-height: 44px !important;
        max-height: 44px !important;
        padding: 0 12px !important;
        line-height: 1 !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        border-radius: 8px !important;
        box-sizing: border-box !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        margin: 0 !important;
    }}
    /* 변경사항 저장 — 보라 채움 */
    .stButton > button[kind="primary"] {{
        background: {PRIMARY} !important;
        border: 1px solid {PRIMARY} !important;
        color: white !important;
        box-shadow: 0 2px 8px rgba(91, 67, 201, 0.22);
    }}
    .stButton > button[kind="primary"]:hover {{
        background: {PRIMARY_DARK} !important;
        border-color: {PRIMARY_DARK} !important;
        box-shadow: 0 4px 12px rgba(91, 67, 201, 0.32);
    }}
    /* 계약 메타 수정 popover — 보라 아웃라인 */
    div[data-testid="stPopover"] button {{
        background: white !important;
        color: {PRIMARY} !important;
        border: 1px solid {PRIMARY} !important;
        box-shadow: none !important;
    }}
    div[data-testid="stPopover"] button:hover {{
        background: {PRIMARY_LIGHT} !important;
        border-color: {PRIMARY_DARK} !important;
        color: {PRIMARY_DARK} !important;
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

# 직전 실행(동기화 등)의 결과 메시지 — st.rerun() 이후에도 1회 노출되도록 세션에 보관.
# (st.rerun() 직전에 띄운 success/info/error는 즉시 재실행으로 지워지므로 여기서 렌더)
_pending_msg = st.session_state.pop("_sync_msg", None)
if _pending_msg:
    _kind, _text = _pending_msg
    getattr(st.sidebar, _kind)(_text)

if st.sidebar.button(
    "🔄 데이터 동기화",
    use_container_width=True,
    help=(
        "Notion 영업현황을 Sheets에 전체 반영합니다. "
        "신규 계약·결제 회차 추가 → 메타(고객기관·건명·서비스명·신규갱신·정산유형·계약일·총금액·구독시작/종료일) 갱신 → "
        "분납회차 갱신(부족한 결제 회차 row 자동 생성) → 캐시 새로고침 순으로 실행."
    ),
):
    try:
        with st.spinner("Notion 영업현황 조회 중..."):
            notion_df = load_sales_data()

        with st.spinner("신규 데이터 수집 중..."):
            added_c, added_p = ct.sync_from_notion(notion_df)

        with st.spinner("기존 데이터 갱신 중..."):
            meta_n = ct.resync_meta_from_notion(notion_df)
            inst_upd, inst_added = ct.resync_installments_from_notion(notion_df)

        parts = []
        if added_c > 0 or added_p > 0:
            parts.append(f"신규 계약 {added_c}건 · 결제 회차 {added_p}건 추가")
        if meta_n > 0:
            parts.append(f"메타 {meta_n}건 갱신")
        if inst_upd > 0:
            parts.append(f"분납회차 {inst_upd}건 갱신 (회차 {inst_added}개 추가)")
        if parts:
            st.session_state["_sync_msg"] = ("success", "✅ " + " · ".join(parts))
        else:
            st.session_state["_sync_msg"] = (
                "info",
                "변경 사항 없음 (모두 최신). Notion에 새 '성공' 계약이 있는데도 이 메시지가 "
                "나오면, 아래 **'🔌 Notion 연결 진단'**으로 앱이 2026 DB를 보는지 확인하세요.",
            )

        ct.invalidate_cache()
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        msg = str(e)
        if "429" in msg or "Quota" in msg:
            st.session_state["_sync_msg"] = (
                "error",
                "⏳ Google Sheets 분당 읽기 할당량 초과. **1분 후 다시 시도**해주세요. "
                "(연속 클릭·다른 페이지 동시 로드가 누적되면 발생)",
            )
        else:
            st.session_state["_sync_msg"] = ("error", f"동기화 실패: {msg}")
        st.rerun()

# Notion 연결 진단 — 앱의 토큰이 각 연도 DB를 실제로 보는지 즉석 점검.
# '동기화해도 변경 사항 없음'이 반복될 때 앱이 최신 데이터를 못 보는지 확인용.
with st.sidebar.expander("🔌 Notion 연결 진단"):
    st.caption(
        "앱의 Notion 토큰이 각 연도 DB를 조회할 수 있는지, 그리고 앱이 보는 "
        "'최신 추가일'이 언제까지인지 확인합니다. 최신 추가일이 실제 노션보다 "
        "과거에 멈춰 있거나 '실패'가 뜨면, 해당 DB에 integration 연결이 끊긴 것입니다 "
        "(노션에서 DB → ••• → 연결(Connections)에 앱 integration 추가 필요)."
    )
    if st.button("연결 점검 실행", use_container_width=True, key="notion_diag_btn"):
        with st.spinner("Notion 각 DB 조회 중..."):
            try:
                st.session_state["_notion_diag"] = notion_source_status()
            except Exception as e:
                st.session_state["_notion_diag"] = [
                    {"label": "오류", "ok": False, "error": f"{type(e).__name__}: {e}"}
                ]
    for _row in st.session_state.get("_notion_diag", []):
        if _row.get("ok"):
            _latest = _row.get("latest")
            _latest_txt = str(_latest)[:10] if _latest else "행 없음"
            _nm = _row.get("latest_name") or "-"
            st.success(f"**{_row['label']}**: 접근 OK · 최신 추가 {_latest_txt} ({_nm})")
        else:
            st.error(f"**{_row['label']}**: 접근 실패 — {_row.get('error', '')}")

# 시트 쓰기/읽기 진단 — 동기화는 '성공'인데 화면·재조회에 반영이 안 될 때,
# 앱이 실제로 쓰는 시트와 '쓰기→즉시 읽기'가 반영되는지 확인.
with st.sidebar.expander("🧪 시트 쓰기 진단"):
    st.caption(
        "동기화가 '추가/갱신 N건'이라는데 화면에 안 나타날 때 사용합니다. "
        "앱이 실제로 어떤 시트를 쓰는지, 방금 쓴 값이 즉시 다시 읽히는지 확인합니다."
    )
    if st.button("시트 점검 실행", use_container_width=True, key="sheet_diag_btn"):
        with st.spinner("시트 쓰기/읽기 테스트 중..."):
            st.session_state["_sheet_diag"] = ct.sheet_diagnostics()
    _sd = st.session_state.get("_sheet_diag")
    if _sd:
        if _sd.get("error"):
            st.error(f"진단 실패: {_sd['error']}")
        else:
            _rb = _sd.get("write_readback_ok")
            if _rb:
                st.success("쓰기→읽기 반영: 정상 ✅")
            else:
                st.error(
                    "쓰기→읽기 반영: **실패** ❌ — 시트에 쓴 값이 다시 읽을 때 "
                    "안 나타납니다 (읽기/쓰기 대상 불일치 의심)."
                )
            if _sd.get("spreadsheet_url"):
                st.markdown(f"🔗 **[이 시트 열기]({_sd['spreadsheet_url']})** — 앱이 실제로 읽고/쓰는 시트")
            st.write(
                f"- 스프레드시트: **{_sd.get('spreadsheet_title')}** "
                f"(`{_sd.get('spreadsheet_id')}`, secret=`{_sd.get('secret_sheet_id')}`)\n"
                f"- 워크시트: **{_sd.get('worksheet_title')}** · 행수 {_sd.get('row_count')} "
                f"→ append 후 {_sd.get('row_count_after_append')}\n"
                f"- 시트가 보는 최신 계약일: **{_sd.get('max_계약일')}** · "
                f"최신 구독종료일: **{_sd.get('max_구독종료일')}**"
            )
            if _sd.get("cleanup_error"):
                st.caption(f"(마커 정리 경고: {_sd['cleanup_error']})")

# 시트 정리(재구성) — 떠도는 값·빈 갭·밀린 중복 행 제거. 2단계(미리보기 → 실행).
with st.sidebar.expander("🧹 시트 정리(재구성)"):
    st.caption(
        "반복 동기화로 시트에 쌓인 떠도는 숫자·빈 행·열이 밀린 중복 행을 제거합니다. "
        "**기존 유효 계약·수기 입력은 보존**하며, 깨진 행만 정리합니다. "
        "먼저 미리보기로 무엇이 지워질지 확인하세요."
    )
    if st.button("🔍 정리 미리보기", use_container_width=True, key="repair_preview_btn"):
        with st.spinner("시트 분석 중..."):
            try:
                st.session_state["_repair_preview"] = ct.repair_sheets(dry_run=True)
            except Exception as e:
                st.error(f"미리보기 실패: {e}")
    _rp = st.session_state.get("_repair_preview")
    if _rp:
        st.write(
            f"**Contracts**: {_rp['contracts_raw']}행 → 유지 **{_rp['contracts_kept']}** "
            f"(깨짐 {_rp['contracts_removed_junk']} · 중복 {_rp['contracts_removed_dup']} 제거)\n\n"
            f"**Payments**: {_rp['payments_raw']}행 → 유지 **{_rp['payments_kept']}** "
            f"(깨짐 {_rp['payments_removed_junk']} · 중복 {_rp['payments_removed_dup']} · "
            f"고아 {_rp['payments_removed_orphan']} 제거)"
        )
        _to_remove = (
            _rp["contracts_removed_junk"] + _rp["contracts_removed_dup"]
            + _rp["payments_removed_junk"] + _rp["payments_removed_dup"]
            + _rp["payments_removed_orphan"]
        )
        if _to_remove == 0:
            st.success("정리할 깨진 행이 없습니다. 시트는 이미 깔끔합니다 ✅")
        else:
            st.warning(f"위 내용대로 **{_to_remove}행**을 제거하고 재작성합니다. 되돌릴 수 없습니다.")
            if st.button("🧹 정리 실행", type="primary", use_container_width=True, key="repair_run_btn"):
                with st.spinner("시트 재구성 중..."):
                    try:
                        _res = ct.repair_sheets(dry_run=False)
                        st.session_state["_sync_msg"] = (
                            "success",
                            f"✅ 시트 정리 완료 — Contracts {_res['contracts_kept']}행 · "
                            f"Payments {_res['payments_kept']}행 유지. 이제 '데이터 동기화'로 "
                            f"최신 계약을 다시 가져오세요.",
                        )
                        del st.session_state["_repair_preview"]
                        ct.invalidate_cache()
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"정리 실패: {e}")

# 노션에서 삭제·상태변경된 시트 row 정리 — 2단계(미리보기 → 실제 삭제)
with st.sidebar.expander("🧹 노션 삭제 row 정리"):
    st.caption(
        "노션에서 페이지를 삭제했거나 상태를 confirmed 외로 바꾼 시트 row를 정리합니다. "
        "수동 입력 row(notion_id 없음)는 건드리지 않습니다."
    )
    if st.button("🔍 미리보기", use_container_width=True, key="orphan_preview_btn"):
        with st.spinner("노션 조회 + 비교 중..."):
            try:
                _notion_df = load_sales_data()
                _orphans = ct.find_orphan_contracts(_notion_df)
                st.session_state["_orphans_preview"] = _orphans
            except Exception as e:
                st.error(f"조회 실패: {e}")

    if "_orphans_preview" in st.session_state:
        _orphans = st.session_state["_orphans_preview"]
        if _orphans.empty:
            st.success("✅ 정리할 row 없음 — 모두 노션과 일치")
            if st.button("닫기", use_container_width=True, key="orphan_close_btn"):
                del st.session_state["_orphans_preview"]
                st.rerun()
        else:
            st.warning(f"⚠️ 정리 대상 **{len(_orphans)}건**")
            for _, _r in _orphans.head(15).iterrows():
                _name = _r.get("건명") or "(이름 없음)"
                _cust = _r.get("고객기관") or "-"
                _nid_short = str(_r.get("notion_id") or "")[:8]
                st.caption(f"• {str(_name)[:25]} | {str(_cust)[:12]} | {_nid_short}…")
            if len(_orphans) > 15:
                st.caption(f"… 외 {len(_orphans) - 15}건")
            st.markdown("---")
            if st.button("🗑️ 실제 삭제", type="primary", use_container_width=True, key="orphan_delete_btn"):
                with st.spinner(f"{len(_orphans)}건 삭제 중..."):
                    try:
                        _cids = _orphans["contract_id"].tolist()
                        _dc, _dp = ct.delete_contracts_by_ids(_cids)
                        st.success(f"✅ 계약 {_dc}건 + 결제 회차 {_dp}건 삭제")
                        del st.session_state["_orphans_preview"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"삭제 실패: {e}")
            if st.button("취소", use_container_width=True, key="orphan_cancel_btn"):
                del st.session_state["_orphans_preview"]
                st.rerun()

# ============== 데이터 로드 ==============
try:
    contracts_df = ct.filter_active_contracts(ct.load_contracts())
    payments_df = ct.load_payments()
except Exception as e:
    import traceback
    st.error(f"Google Sheets 연결 실패: {type(e).__name__}: {e!r}")
    st.code(traceback.format_exc(), language="python")

    # 디버그: secrets 상태 확인
    with st.expander("🔧 디버그 정보", expanded=True):
        try:
            secret_keys = list(st.secrets.keys())
            st.write("**secrets 최상위 키:**", secret_keys)
            if "CONTRACTS_SHEET_ID" in st.secrets:
                sid = st.secrets["CONTRACTS_SHEET_ID"]
                st.write(f"**CONTRACTS_SHEET_ID**: `{sid[:8]}...{sid[-4:]}` (길이 {len(sid)})")
            else:
                st.warning("CONTRACTS_SHEET_ID 없음")
            if "gcp_service_account" in st.secrets:
                sa = dict(st.secrets["gcp_service_account"])
                st.write("**gcp_service_account 키:**", list(sa.keys()))
                if "private_key" in sa:
                    pk = sa["private_key"]
                    st.write(
                        f"**private_key 길이**: {len(pk)}자, "
                        f"**시작**: `{pk[:30]}`, "
                        f"**\\n 포함**: {'\\n' in pk}, "
                        f"**실제 줄바꿈 포함**: {chr(10) in pk}"
                    )
                if "client_email" in sa:
                    st.write(f"**client_email**: {sa['client_email']}")
            else:
                st.warning("gcp_service_account 블록 없음")
        except Exception as e2:
            st.error(f"디버그 정보 수집 실패: {e2}")
    st.stop()

if contracts_df.empty:
    st.info(
        "👋 아직 등록된 계약이 없습니다. 좌측 사이드바의 "
        "**'데이터 동기화'** 버튼을 눌러 Notion에서 가져오세요."
    )
    st.stop()

# ============== 상단 KPI (계약일 기간 필터 적용 — 진행중 + 종료 포함) ==============
_applied_inv_for_kpi = st.session_state.get("inv_applied")
_kpi_contracts = contracts_df
_kpi_payments = payments_df

if _applied_inv_for_kpi:
    _ks, _ke = _applied_inv_for_kpi["start"], _applied_inv_for_kpi["end"]
    _kpi_contracts = contracts_df[
        contracts_df["계약일"].notna()
        & (contracts_df["계약일"].dt.date >= _ks)
        & (contracts_df["계약일"].dt.date <= _ke)
    ]
    _matched_kpi_cids = set(_kpi_contracts["contract_id"].unique())
    _kpi_payments = (
        payments_df[payments_df["contract_id"].isin(_matched_kpi_cids)]
        if not payments_df.empty else payments_df
    )

total_amount = _kpi_contracts["총금액"].sum()
total_paid = ct.effective_paid_amount(_kpi_payments)
total_unpaid = total_amount - total_paid
collection_rate = (total_paid / total_amount * 100) if total_amount > 0 else 0

_kpi_caption = ""
if _applied_inv_for_kpi:
    _kpi_caption = (
        f"<div style='font-size:0.75rem;color:#8B8A95;margin:-8px 0 6px'>"
        f"📅 계약일 {_applied_inv_for_kpi['start']} ~ {_applied_inv_for_kpi['end']} 기간 기준</div>"
    )
    st.markdown(_kpi_caption, unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.markdown(
    f'<div class="kpi-box"><div class="kpi-label">전체 계약</div>'
    f'<div class="kpi-value">{len(_kpi_contracts)}건</div></div>',
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

# ============== 계약 검색 ==============
# 다른 페이지(회계 관리 등)에서 ?q=<text>로 진입하면 그 텍스트로 검색어 자동 설정
_q_param = st.query_params.get("q", "")
if _q_param and st.session_state.get("contract_search", "") != _q_param:
    st.session_state["contract_search"] = _q_param


def _clear_contract_search():
    st.session_state["contract_search"] = ""
    try:
        del st.query_params["q"]
    except KeyError:
        pass


col_in, col_clear = st.columns([6, 1])
with col_in:
    st.text_input(
        "고객명 또는 계약명 키워드",
        key="contract_search",
        placeholder="예: 박**병원, 닥터디아이, ConnectCare ...",
        help="고객기관·건명·서비스명에서 부분 일치 검색 (대소문자 무시)",
    )
with col_clear:
    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
    st.button(
        "↺ 전체 보기",
        on_click=_clear_contract_search,
        use_container_width=True,
        disabled=not st.session_state.get("contract_search", "").strip(),
        help="검색어를 지우고 전체 계약 목록으로 돌아갑니다",
    )

# ----- 계약일 기간 필터 -----
_cdates = contracts_df["계약일"].dropna() if not contracts_df.empty else pd.Series(dtype="datetime64[ns]")
applied_inv_filter = None
if not _cdates.empty:
    _inv_min = _cdates.min().date()
    _inv_max = _cdates.max().date()
    _today = date.today()
    # 종료일 상한을 오늘까지 확장 — 아직 계약일이 오늘 이후가 없더라도 오늘까지 선택 가능.
    # 시작일 상한도 같이 오늘까지 허용.
    _range_max = max(_inv_max, _today)

    if "inv_start" not in st.session_state:
        st.session_state["inv_start"] = _inv_min
    if "inv_end" not in st.session_state:
        st.session_state["inv_end"] = _today

    _fc = st.columns([1.5, 0.2, 1.5, 4, 1, 1])
    with _fc[0]:
        st.date_input(
            "📅 시작일",
            min_value=_inv_min, max_value=_range_max,
            key="inv_start",
        )
    with _fc[1]:
        st.markdown(
            "<div style='text-align:center;color:#8B8A95;font-size:1.3rem;"
            "line-height:40px;margin-top:28px'>~</div>",
            unsafe_allow_html=True,
        )
    with _fc[2]:
        st.date_input(
            "📅 종료일",
            min_value=_inv_min, max_value=_range_max,
            key="inv_end",
        )
    with _fc[4]:
        st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
        if st.button("적용", use_container_width=True, key="inv_apply_btn", type="primary"):
            st.session_state["inv_applied"] = {
                "start": st.session_state["inv_start"],
                "end": st.session_state["inv_end"],
            }
    with _fc[5]:
        st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
        if st.session_state.get("inv_applied"):
            if st.button("해제", use_container_width=True, key="inv_clear_btn"):
                st.session_state.pop("inv_applied", None)
                st.rerun()

    applied_inv_filter = st.session_state.get("inv_applied")

# ----- 상태 필터 (세금계산서 발행 · 입금 · 결제방법) -----
fc1, fc2, fc3 = st.columns(3)
issue_filter = fc1.multiselect(
    "세금계산서 발행",
    options=["발행 완료", "부분 발행", "미발행"],
    default=[],
    placeholder="전체 (필터 없음)",
    help="회차 단위로 집계: 전부 발행 / 일부 발행 / 전혀 미발행",
)
paid_filter = fc2.multiselect(
    "입금",
    options=["입금 완료", "부분 입금", "미입금"],
    default=[],
    placeholder="전체 (필터 없음)",
    help="회차 단위로 집계: 전부 완료 / 일부 완료 / 전혀 미완료",
)
method_filter = fc3.multiselect(
    "결제 방법",
    options=ct.PAYMENT_METHODS + ["미입력"],
    default=[],
    placeholder="전체 (필터 없음)",
    help="계약 단위 결제 방법 (세금계산서·계산서·카드결제, 미입력)",
)

search_query = st.session_state.get("contract_search", "").strip()

if search_query:
    q = search_query.lower()

    def _matches(row):
        for col in ("고객기관", "건명", "서비스명"):
            val = row.get(col, "")
            if val and q in str(val).lower():
                return True
        return False

    customer_contracts = contracts_df[contracts_df.apply(_matches, axis=1)]
else:
    customer_contracts = contracts_df


def _issue_state(cid: str) -> str | None:
    """계약의 발행 상태: '발행 완료' / '부분 발행' / '미발행'. 회차 없으면 None."""
    rows = payments_df[payments_df["contract_id"] == cid] if not payments_df.empty else pd.DataFrame()
    if rows.empty:
        return None
    issued = int(rows["발행일"].notna().sum())
    total = len(rows)
    if issued == 0:
        return "미발행"
    if issued == total:
        return "발행 완료"
    return "부분 발행"


def _paid_state(cid: str) -> str | None:
    rows = payments_df[payments_df["contract_id"] == cid] if not payments_df.empty else pd.DataFrame()
    if rows.empty:
        return None
    paid = int(rows["입금완료"].sum())
    total = len(rows)
    if paid == 0:
        return "미입금"
    if paid == total:
        return "입금 완료"
    return "부분 입금"


if (issue_filter or paid_filter or method_filter) and not customer_contracts.empty:
    mask = pd.Series(True, index=customer_contracts.index)
    if issue_filter:
        states = customer_contracts["contract_id"].apply(_issue_state)
        mask &= states.isin(issue_filter)
    if paid_filter:
        states = customer_contracts["contract_id"].apply(_paid_state)
        mask &= states.isin(paid_filter)
    if method_filter:
        # '미입력' → 빈 문자열 매칭
        _targets = {("" if m == "미입력" else m) for m in method_filter}
        mask &= (
            customer_contracts["결제방법"].fillna("").astype(str).str.strip().isin(_targets)
        )
    customer_contracts = customer_contracts[mask]

# 계약일 기간 필터 — 적용된 경우 계약일이 해당 범위에 있는 계약만 통과
if applied_inv_filter and not customer_contracts.empty:
    _s, _e = applied_inv_filter["start"], applied_inv_filter["end"]
    customer_contracts = customer_contracts[
        customer_contracts["계약일"].notna()
        & (customer_contracts["계약일"].dt.date >= _s)
        & (customer_contracts["계약일"].dt.date <= _e)
    ]

# 검색 결과 요약 (검색어 입력 시)
if search_query:
    cust_total = customer_contracts["총금액"].sum()
    cust_paid = ct.effective_paid_amount(
        payments_df[payments_df["contract_id"].isin(customer_contracts["contract_id"])]
    ) if not payments_df.empty else 0
    cust_unpaid = cust_total - cust_paid
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric(f"'{search_query}' 검색 결과", f"{len(customer_contracts)}건")
    cc2.metric("총 계약금", f"{cust_total:,.0f}원")
    cc3.metric(
        "미수금",
        f"{cust_unpaid:,.0f}원",
        delta=f"-{cust_unpaid/cust_total*100:.0f}%" if cust_total else "0%",
    )

if search_query and customer_contracts.empty:
    st.warning(f"'{search_query}'과(와) 일치하는 계약이 없습니다.")

# ============== 진행중 / 종료 분리 ==============
# 종료 조건: 계약의 모든 결제 회차에 대해 필수 필드가 모두 입력됨.
#   - 일반 row: 발행일, 입금일, 금액(매출액), 단가, 고객입금액, 결제방법
#   - 대납액 row: 입금일, 단가, 고객입금액 (+ 결제방법="대납액") — 매출액·발행일 제외
# 회차 하나라도 미충족이면 진행중으로 간주.
_today = pd.Timestamp.today().normalize()

_DATE_FIELDS = ("발행일", "입금일")
_AMOUNT_FIELDS = ("금액", "단가", "고객입금액")
# 대납액 row 전용 — 매출액·발행일 없이도 종료 판정
_DAENAP_DATE_FIELDS = ("입금일",)
_DAENAP_AMOUNT_FIELDS = ("단가", "고객입금액")


def _all_fields_filled(cid: str) -> bool:
    pays = payments_df[payments_df["contract_id"] == cid] if not payments_df.empty else pd.DataFrame()
    if pays.empty:
        return False
    for _, r in pays.iterrows():
        is_daenap = str(r.get("결제방법") or "").strip() == "대납액"
        date_fields = _DAENAP_DATE_FIELDS if is_daenap else _DATE_FIELDS
        amount_fields = _DAENAP_AMOUNT_FIELDS if is_daenap else _AMOUNT_FIELDS
        # 날짜 필드: NaT/빈셀이면 미입력
        for f in date_fields:
            v = r.get(f)
            if pd.isna(v) or (isinstance(v, str) and not v.strip()):
                return False
        # 금액 필드: 빈셀 또는 0이면 미입력
        for f in amount_fields:
            v = pd.to_numeric(r.get(f), errors="coerce")
            if pd.isna(v) or v == 0:
                return False
        # 결제방법: 빈 문자열이면 미입력 (대납액 row는 이미 "대납액"이라 자동 충족)
        if not str(r.get("결제방법") or "").strip():
            return False
    return True


_ended_mask = customer_contracts["contract_id"].apply(_all_fields_filled)
_active_contracts = customer_contracts[~_ended_mask]
_ended_contracts = customer_contracts[_ended_mask]

# 탭(진행중/종료) + 모두 펼치기/접기 — 한 줄에 좌우 배치
st.markdown(
    """
    <style>
    /* 모두 펼치기/접기 버튼 라벨 한 줄 유지 */
    div[data-testid="stHorizontalBlock"] button p {
        white-space: nowrap !important;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* 탭(segmented_control) row의 모든 컬럼 — flex vertical center */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSegmentedControl"])
        > div[data-testid="stColumn"] {
        display: flex !important;
        align-items: center !important;
    }
    /* 전체 펼치기/접기 버튼 — 커스텀 height 오버라이드 없이 Streamlit 기본 스타일 사용.
       버튼 안 모든 요소에 nowrap 강제해 wrap으로 인한 높이 불일치 방지.
       (라벨에도 NBSP를 써 브라우저가 공백에서 break하지 못하게 이중 방어) */
    div.st-key-expand_all_btn button,
    div.st-key-expand_all_btn button *,
    div.st-key-collapse_all_btn button,
    div.st-key-collapse_all_btn button * {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# st.tabs는 rerun 시 첫 탭으로 리셋되므로 session_state 유지되는 segmented_control 사용.
# default 인자는 매 rerun마다 session_state를 덮어쓸 수 있으므로 명시적 초기화로 분리.
if "contract_tab_choice" not in st.session_state:
    st.session_state["contract_tab_choice"] = "active"

_tab_col, _spacer_col, _exp_col, _col_col = st.columns([4, 6, 1, 1])

with _tab_col:
    _selected_tab = st.segmented_control(
        "계약 상태 탭",
        options=["active", "ended"],
        format_func=lambda x: (
            f"📂 진행 중 ({len(_active_contracts)}건)"
            if x == "active"
            else f"🗂️ 종료 ({len(_ended_contracts)}건)"
        ),
        key="contract_tab_choice",
        label_visibility="collapsed",
    )

with _exp_col:
    if st.button("⏬", help="전체 펼치기", use_container_width=True, key="expand_all_btn"):
        for _cid in customer_contracts["contract_id"]:
            st.session_state[f"expand_{_cid}"] = True
        st.rerun()
with _col_col:
    if st.button("⏫", help="전체 접기", use_container_width=True, key="collapse_all_btn"):
        for _cid in customer_contracts["contract_id"]:
            st.session_state[f"expand_{_cid}"] = False
        st.rerun()

# 사용자가 선택 해제(None)한 경우 진행 중으로 fallback
if _selected_tab is None:
    _selected_tab = "active"


def _render_contract_card(c, card_idx: int = 0):
    """단일 계약 카드 렌더링 — 진행중/종료 탭에서 공통 사용.

    card_idx: contract_id 중복 데이터(시트 입력 실수 등)가 있을 때도 widget key
              충돌 방지 위해 row index를 함께 사용. 호출부에서 enumerate로 전달.
    """
    contract_id = c["contract_id"]
    card_uid = "{}__{}".format(contract_id, card_idx)  # widget key용 unique id
    contract_payments = payments_df[payments_df["contract_id"] == contract_id] if not payments_df.empty else pd.DataFrame()
    paid_amount = ct.effective_paid_amount(contract_payments)
    progress = (paid_amount / c["총금액"] * 100) if c["총금액"] > 0 else 0

    # 입금률 배지
    if progress >= 100:
        badge = f"🟢 {progress:.0f}%"
    elif progress > 0:
        badge = f"🟡 {progress:.0f}%"
    else:
        badge = f"🔴 {progress:.0f}%"

    # 카드 박스 — 4등분(계약명·고객·금액·입금률) + 펼침 버튼
    expand_key = f"expand_{card_uid}"
    if expand_key not in st.session_state:
        st.session_state[expand_key] = False
    is_expanded = st.session_state[expand_key]

    with st.container(border=True):
        col_name, col_cust, col_amt, col_rate, col_btn = st.columns([1, 1, 1, 1, 0.18])
        col_name.markdown(f"📄 **{c['건명'] or '—'}**")
        col_cust.markdown(c["고객기관"] or "—")
        col_amt.markdown(f"`{c['총금액']:,.0f}원`")
        col_rate.markdown(badge)
        if col_btn.button(
            "▲" if is_expanded else "▼",
            key=f"toggle_{card_uid}",
            use_container_width=True,
            help="펼치기/접기",
        ):
            st.session_state[expand_key] = not is_expanded
            st.rerun()

    if is_expanded:
        # 계약 정보 — 카드 안에 보조 라벨 + 값 (균일 크기·간격)
        st.markdown(
            "<div style='margin: 8px 0 4px; display: grid; "
            "grid-template-columns: repeat(4, 1fr); gap: 16px; "
            "background: #FAFAFC; border: 1px solid #EDECF1; "
            "border-radius: 8px; padding: 14px 18px;'>"
            f"<div><div style='font-size:0.72rem;color:#6B6A73;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px'>계약일</div>"
            f"<div style='font-size:0.95rem;font-weight:600'>{c['계약일'].strftime('%Y-%m-%d') if pd.notna(c['계약일']) else '—'}</div></div>"
            f"<div><div style='font-size:0.72rem;color:#6B6A73;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px'>서비스</div>"
            f"<div style='font-size:0.95rem;font-weight:600'>{c['서비스명'] or '—'}</div></div>"
            f"<div><div style='font-size:0.72rem;color:#6B6A73;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px'>정산유형</div>"
            f"<div style='font-size:0.95rem;font-weight:600'>{c['정산유형'] or '미입력'}</div></div>"
            f"<div><div style='font-size:0.72rem;color:#6B6A73;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px'>분납 회차</div>"
            f"<div style='font-size:0.95rem;font-weight:600'>"
            f"{int(c['분납회차']) if pd.notna(c['분납회차']) else '—'}회</div></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        # 결제 회차
        st.markdown(
            "<div style='margin: 18px 0 8px; font-weight:700; font-size:1rem'>💳 결제 회차</div>",
            unsafe_allow_html=True,
        )
        if contract_payments.empty:
            st.caption("등록된 결제 회차가 없습니다. ⚙️ 계약 메타에서 분납 회차를 입력하거나 ➕ 회차 추가로 등록하세요.")
        else:
            # 표시용 view: 회차·청구예정일·발행일·결제방법·금액·단가·고객입금액·입금일
            view = contract_payments.sort_values("회차")[[
                "payment_id", "회차", "청구예정일", "발행일", "결제방법",
                "금액", "단가", "고객입금액", "입금일",
            ]].copy()
            view = view.reset_index(drop=True)
            for col in ("청구예정일", "발행일", "입금일"):
                view[col] = pd.to_datetime(view[col], errors="coerce")
            view["금액"] = view["금액"].astype(float).round().astype("Int64")
            view["단가"] = view["단가"].astype(float).round().astype("Int64")
            view["고객입금액"] = view["고객입금액"].astype(float).round().astype("Int64")
            # 결제방법은 payment row 단위 — 시트의 row 값 그대로 사용
            # (해외대조약은 세금계산서/대납액 분리; 그 외는 계약 단위 기본값으로 일괄)
            view["결제방법"] = view["결제방법"].fillna("").astype(str)
            # 단가 0은 빈칸 표시 (수기 입력 전 상태)
            view.loc[view["단가"] == 0, "단가"] = pd.NA
            # 고객입금액 0/빈셀은 빈칸으로 표시 — 자동 fallback 제거.
            # 실제 입금 확인 후 사용자가 수기 입력하는 정책.
            view.loc[view["고객입금액"] == 0, "고객입금액"] = pd.NA
            # 대납액 row는 매출액(금액) 미사용 — 빈칸으로 가림. 단가·고객입금액만 의미 있음.
            # 매출 집계에서도 제외 (home.py 415 라인 + 아래 _is_revenue).
            _daenap_mask = view["결제방법"].astype(str).str.strip() == "대납액"
            view.loc[_daenap_mask, "금액"] = pd.NA

            # data_editor의 미저장 편집 내역을 view에 미리 적용 → 합계 실시간 반영
            _editor_key = f"editor_{card_uid}"
            _view_live = view.copy()
            _editor_state = st.session_state.get(_editor_key, {})
            for _row_idx, _changes in _editor_state.get("edited_rows", {}).items():
                if _row_idx not in _view_live.index:
                    continue
                for _col, _val in _changes.items():
                    if _col in _view_live.columns:
                        _view_live.at[_row_idx, _col] = _val

            # 합계 — 대납액 row 제외 (매출만)
            _is_revenue = _view_live["결제방법"].astype(str).str.strip() != "대납액"
            _sum_금액 = int(pd.to_numeric(_view_live.loc[_is_revenue, "금액"], errors="coerce").fillna(0).sum())
            _sum_단가 = int(pd.to_numeric(_view_live.loc[_is_revenue, "단가"], errors="coerce").fillna(0).sum())
            _sum_고객 = int(pd.to_numeric(_view_live["고객입금액"], errors="coerce").fillna(0).sum())

            def _bulk_apply_method():
                val = st.session_state.get(f"bulk_pm_{card_uid}", "(미선택)")
                new_val = "" if val == "(미선택)" else val
                # 계약 단위 기본값 저장
                ct.update_contract_meta(contract_id, 결제방법=new_val)
                # 모든 payment row의 결제방법도 일괄 변경 (해외대조약 분리 정보는 덮어씀)
                for _pid in view["payment_id"]:
                    ct.update_payment_fields(_pid, 결제방법=new_val)
                st.rerun()

            # 일괄 선택 기본값: 모든 row가 같은 값이면 그 값, 다르면 (미선택)
            _row_methods = {str(m or "").strip() for m in view["결제방법"]}
            _curr_method = _row_methods.pop() if len(_row_methods) == 1 else ""
            _options_pm = ["(미선택)"] + ct.PAYMENT_METHODS
            _idx_pm = _options_pm.index(_curr_method) if _curr_method in _options_pm else 0

            # 폭 비율 — data_editor의 픽셀 폭과 매칭
            # 50 / 150+150+130=430 / 150 / 150 / 150 / 150
            _h_cols = st.columns([0.5, 4.3, 1.5, 1.5, 1.5, 1.5])

            # selectbox 높이(~38px)와 맞추기 + 시각 통일 (border + bg)
            _cell_h = 38
            _flex_base = (
                f"height:{_cell_h}px;display:flex;align-items:center;"
                "padding:0 12px;border-radius:6px;font-size:0.85rem;white-space:nowrap;"
                "overflow:hidden;text-overflow:ellipsis;box-sizing:border-box;"
                "border:1px solid #EDECF1;"
            )

            # 합계 row 안의 모든 셀(selectbox 포함)을 같은 라인에 정렬
            # — selectbox가 있는 row의 stColumn을 stretch + 컨텐츠를 vertical-center
            st.markdown(
                """
                <style>
                div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"])
                    > div[data-testid="stColumn"] {
                    align-self: stretch !important;
                    display: flex !important;
                    align-items: center !important;
                }
                div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"])
                    > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
                    width: 100% !important;
                    gap: 0 !important;
                }
                div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"])
                    [data-testid="stMarkdownContainer"],
                div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"])
                    [data-testid="stSelectbox"] {
                    margin: 0 !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            with _h_cols[0]:
                st.markdown(
                    f"<div style='background:#F1EEFB;color:#4A35B0;font-weight:700;"
                    f"justify-content:center;{_flex_base}'>합계</div>",
                    unsafe_allow_html=True,
                )

            with _h_cols[1]:
                st.selectbox(
                    "결제방법 일괄",
                    options=_options_pm,
                    index=_idx_pm,
                    key=f"bulk_pm_{card_uid}",
                    on_change=_bulk_apply_method,
                    label_visibility="collapsed",
                    help="선택 시 모든 회차에 일괄 적용",
                )

            _num_cell_style = (
                "background:white;color:#1E1B2E;font-weight:700;"
                "justify-content:flex-end;" + _flex_base
            )
            for _i, _v in enumerate([_sum_금액, _sum_단가, _sum_고객]):
                with _h_cols[_i + 2]:
                    st.markdown(
                        f"<div style='{_num_cell_style}'>{_v:,}원</div>",
                        unsafe_allow_html=True,
                    )
            with _h_cols[5]:
                pass  # 입금일 빈 자리

            edited = st.data_editor(
                view,
                column_config={
                    "payment_id": None,
                    "회차": st.column_config.TextColumn("회차", disabled=True, width=50),
                    "청구예정일": st.column_config.DateColumn(
                        "청구 예정일",
                        format="YYYY-MM-DD",
                        width=150,
                        help="세금계산서 발행 예정 날짜",
                    ),
                    "발행일": st.column_config.DateColumn(
                        "세금계산서 발행일",
                        format="YYYY-MM-DD",
                        width=150,
                    ),
                    "결제방법": st.column_config.SelectboxColumn(
                        "결제 방법",
                        options=ct.PAYMENT_METHODS,
                        width=130,
                        help="계약 단위. 어느 행이든 수정하면 저장 시 계약 단위로 반영됩니다.",
                    ),
                    "금액": st.column_config.NumberColumn(
                        "매출액 (부가세포함)",
                        format="localized",
                        width=150,
                        help="세금계산서 발행 금액. 결제방법이 '대납액'인 회차는 매출이 아니므로 입력 무시 + 자동 정리됩니다 (단가·고객입금액만 사용).",
                    ),
                    "단가": st.column_config.NumberColumn(
                        "단가",
                        format="localized",
                        width=150,
                        help="회차 단위 단가. 해외대조약은 세금계산서/대납액 각각 독립 입력하세요.",
                    ),
                    "고객입금액": st.column_config.NumberColumn(
                        "고객 입금액",
                        format="localized",
                        width=150,
                        help="실제 입금된 금액 (관세·부가세 대납 등으로 발행액과 다를 수 있음)",
                    ),
                    "입금일": st.column_config.DateColumn(
                        "입금일",
                        format="YYYY-MM-DD",
                        width=150,
                        help="날짜를 입력하면 자동으로 입금완료(✅) 처리됩니다",
                    ),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key=f"editor_{card_uid}",
            )

            # 편집 결과 실시간 상태 미리보기
            status_emojis = ["✅ 입금" if pd.notna(d) else "⬜ 미입금" for d in edited["입금일"]]
            st.markdown(
                f"<div style='margin: 6px 0 14px; font-size:0.78rem; color:#6B6A73'>"
                f"실시간 미리보기 · {' · '.join(f'{r}회차 {s}' for r, s in zip(edited['회차'], status_emojis))}"
                f"</div>",
                unsafe_allow_html=True,
            )

            btn_cols = st.columns([1, 1, 1])
            with btn_cols[0]:
                with st.popover("⚙️ 계약 메타 수정", use_container_width=True):
                    new_분납 = st.number_input(
                        "분납 회차 (분할정산: 2 또는 3, 월납: 12 등) — 입력 시 부족한 회차가 자동 생성됩니다",
                        min_value=0, max_value=24,
                        value=int(c["분납회차"]) if pd.notna(c["분납회차"]) else 0,
                        key=f"분납_{card_uid}",
                    )
                    st.caption("💡 단가는 결제 회차 표에서 회차별로 입력하세요 (해외대조약은 세금계산서/대납액 독립)")
                    _curr_pay_method = str(c.get("결제방법") or "").strip()
                    _pay_options = ["(미선택)"] + ct.PAYMENT_METHODS
                    _pay_idx = (
                        _pay_options.index(_curr_pay_method)
                        if _curr_pay_method in _pay_options else 0
                    )
                    new_결제방법 = st.selectbox(
                        "결제 방법",
                        options=_pay_options,
                        index=_pay_idx,
                        key=f"결제방법_{card_uid}",
                    )
                    new_구독시작 = st.date_input(
                        "구독 시작일",
                        value=c["구독시작일"].date() if pd.notna(c["구독시작일"]) else None,
                        key=f"시작_{card_uid}",
                    )
                    new_구독종료 = st.date_input(
                        "구독 종료일",
                        value=c["구독종료일"].date() if pd.notna(c["구독종료일"]) else None,
                        key=f"종료_{card_uid}",
                    )
                    new_메모 = st.text_area("메모", value=c.get("메모", "") or "", key=f"memo_{card_uid}")
                    if st.button("저장", key=f"save_{card_uid}"):
                        ct.update_contract_meta(
                            contract_id,
                            분납회차=new_분납 if new_분납 > 0 else "",
                            결제방법=(new_결제방법 if new_결제방법 != "(미선택)" else ""),
                            구독시작일=new_구독시작,
                            구독종료일=new_구독종료,
                            메모=new_메모,
                        )
                        if new_분납 > 0:
                            added = ct.ensure_payment_rows(contract_id, new_분납, c["총금액"])
                            if added > 0:
                                st.success(f"✅ 메타 저장 + 회차 {added}개 자동 생성")
                            else:
                                st.success("✅ 메타 저장 (회차는 이미 충분히 있음)")
                        else:
                            st.success("✅ 저장 완료")
                        st.rerun()

                    # ----- 위험 영역: 계약 삭제 -----
                    st.markdown("---")
                    st.markdown(
                        "<div style='color:#B91C1C;font-weight:700;margin-bottom:6px'>⚠️ 위험 영역</div>"
                        "<div style='font-size:0.82rem;color:#6B6A73;line-height:1.5'>"
                        "이 계약과 연결된 모든 결제 회차가 시트에서 영구 삭제됩니다. "
                        "매칭된 카드결제가 있으면 매칭_상태가 '미매칭'으로 되돌아갑니다."
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    _confirm = st.checkbox(
                        "삭제 확인 — 이 동작은 되돌릴 수 없음",
                        key=f"del_confirm_{card_uid}",
                    )
                    if st.button(
                        "🗑️ 계약 + 회차 영구 삭제",
                        key=f"del_btn_{card_uid}",
                        disabled=not _confirm,
                        type="secondary",
                        use_container_width=True,
                    ):
                        try:
                            res = ct.delete_contract(contract_id)
                            st.success(
                                f"✅ 삭제 완료 — 계약 {res['contract']}건 · "
                                f"회차 {res['payments']}개 · 카드매칭 해제 {res['cards_unmatched']}건"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 실패: {type(e).__name__}: {e}")
            save_clicked = btn_cols[1].button(
                "💾 변경사항 저장",
                key=f"save_edit_{card_uid}",
                type="primary",
                use_container_width=True,
            )
            if save_clicked:
                contract_changes = []

                # 단가는 payment row 단위 — per-row diff에서 처리
                # (해외대조약: 세금계산서/대납액 각각 독립 입력)

                # 결제방법은 회차 단위로 변경되도록 per-row diff에서 처리
                # (해외대조약: 세금계산서/대납액 분리; 그 외: 사용자가 직접 수정)

                # 분납회차 12회 + 1회차 청구예정일 입력된 경우 → 2~12회차 청구예정일 자동 채움 (빈 셀만)
                try:
                    분납_n = int(c.get("분납회차") or 0)
                except (ValueError, TypeError):
                    분납_n = 0
                if 분납_n == 12 and len(edited) >= 2:
                    edited_sorted = edited.sort_values("회차").reset_index(drop=True)
                    first_date = edited_sorted.loc[0, "청구예정일"]
                    if pd.notna(first_date):
                        for i in range(1, len(edited_sorted)):
                            if pd.isna(edited_sorted.loc[i, "청구예정일"]):
                                edited_sorted.loc[i, "청구예정일"] = (
                                    first_date + pd.DateOffset(months=i)
                                )
                        # 원래 index 순서 유지하며 edited에 반영
                        edited = edited_sorted.set_index(
                            pd.Index(range(len(edited_sorted)))
                        )

                changes_count = 0
                for idx in edited.index:
                    orig = view.loc[idx]
                    new = edited.loc[idx]
                    pid = orig["payment_id"]
                    is_daenap = str(new.get("결제방법") or "").strip() == "대납액"
                    diffs = {}
                    for col in ("청구예정일", "발행일", "결제방법", "입금일", "금액", "단가", "고객입금액"):
                        # 대납액 row의 매출액은 사용자 입력 무시 — 아래에서 시트 잔존값 정리만 처리
                        if is_daenap and col == "금액":
                            continue
                        a, b = orig[col], new[col]
                        if pd.isna(a) and pd.isna(b):
                            continue
                        if pd.isna(a) != pd.isna(b) or a != b:
                            if isinstance(b, pd.Timestamp) and pd.notna(b):
                                diffs[col] = b.date()
                            elif pd.isna(b):
                                diffs[col] = ""
                            else:
                                diffs[col] = b
                    # 대납액 row의 매출액은 view에서 가렸지만 시트엔 잔존 가능 → 비우기.
                    # contract_payments(원본)에서 시트값 확인 후 0/None이 아니면 빈값으로 정리.
                    if is_daenap:
                        sheet_row = contract_payments[contract_payments["payment_id"] == pid]
                        if not sheet_row.empty:
                            sheet_금액 = sheet_row.iloc[0].get("금액")
                            try:
                                if pd.notna(sheet_금액) and float(sheet_금액) != 0:
                                    diffs["금액"] = ""
                            except (ValueError, TypeError):
                                pass
                    if diffs:
                        ct.update_payment_fields(pid, **diffs)
                        changes_count += 1

                # 해외대조약: 1회차 세금계산서의 청구예정일/발행일을 대납액 row(들)에 그대로 복사
                if ct.is_overseas(c.get("서비스명")):
                    _first_seg = edited[
                        (edited["회차"].astype(str) == "1")
                        & (edited["결제방법"].astype(str).str.strip() == "세금계산서")
                    ]
                    _daenap = edited[edited["결제방법"].astype(str).str.strip() == "대납액"]
                    if not _first_seg.empty and not _daenap.empty:
                        _seg = _first_seg.iloc[0]
                        _sync = {}
                        for _col in ("청구예정일", "발행일"):
                            _v = _seg[_col]
                            if pd.notna(_v) and isinstance(_v, pd.Timestamp):
                                _sync[_col] = _v.date()
                            else:
                                _sync[_col] = ""
                        for _, _d in _daenap.iterrows():
                            # 이미 같은 값이면 skip (불필요한 시트 write 절약)
                            same = all(
                                (pd.isna(_d[_col]) and _sync[_col] == "")
                                or (
                                    pd.notna(_d[_col])
                                    and isinstance(_d[_col], pd.Timestamp)
                                    and _d[_col].date() == _sync[_col]
                                )
                                for _col in ("청구예정일", "발행일")
                            )
                            if not same:
                                ct.update_payment_fields(_d["payment_id"], **_sync)
                                changes_count += 1
                if changes_count or contract_changes:
                    msg_parts = []
                    if changes_count:
                        msg_parts.append(f"회차 {changes_count}개")
                    if contract_changes:
                        msg_parts.append(f"계약 메타({', '.join(contract_changes)})")
                    st.success(f"✅ {' + '.join(msg_parts)} 변경 저장 완료")
                    # 저장 후 카드 접기
                    st.session_state[f"expand_{card_uid}"] = False
                    st.rerun()
                else:
                    st.info("변경된 내용이 없습니다.")

        if c.get("메모"):
            st.caption(f"📝 메모: {c['메모']}")


if _selected_tab == "ended":
    if _ended_contracts.empty:
        st.info("종료된 계약이 없습니다.")
    else:
        # contract_id가 시트 입력 실수 등으로 중복 가능 — enumerate idx로 widget key 충돌 회피
        _dup_ids = _ended_contracts["contract_id"][_ended_contracts["contract_id"].duplicated()].unique().tolist()
        if _dup_ids:
            st.warning(f"⚠️ 중복된 contract_id 발견 ({len(_dup_ids)}건): {', '.join(map(str, _dup_ids[:5]))}{'...' if len(_dup_ids) > 5 else ''}. Google Sheets에서 정리해주세요.")
        for idx, (_, c) in enumerate(_ended_contracts.iterrows()):
            _render_contract_card(c, card_idx=idx)
else:
    if _active_contracts.empty:
        st.info("진행 중인 계약이 없습니다.")
    else:
        _dup_ids = _active_contracts["contract_id"][_active_contracts["contract_id"].duplicated()].unique().tolist()
        if _dup_ids:
            st.warning(f"⚠️ 중복된 contract_id 발견 ({len(_dup_ids)}건): {', '.join(map(str, _dup_ids[:5]))}{'...' if len(_dup_ids) > 5 else ''}. Google Sheets에서 정리해주세요.")
        for idx, (_, c) in enumerate(_active_contracts.iterrows()):
            _render_contract_card(c, card_idx=idx)

# ============== 푸터 ==============
st.markdown("---")
st.caption(
    f"전체 계약 {len(contracts_df)}건 · 결제 회차 {len(payments_df)}건 · "
    f"캐시 60초 · 출처: Google Sheets (OnesGlobal Contracts)"
)
