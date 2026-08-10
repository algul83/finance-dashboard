"""계약 도메인 로직: Notion 영업현황 → Sheets 동기화 + 결제 회차 관리."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from gsheet_client import get_worksheet

CONFIRMED_STATES = ("성공", "입금완료", "정산완료")

CONTRACT_COLUMNS = [
    "contract_id",      # C{timestamp}
    "notion_id",        # Notion 원본 page id
    "고객기관",
    "건명",
    "서비스명",          # 콤마 join
    "신규갱신",          # 일회성/신규/갱신
    "노션상태",          # 노션 현재 status — 성공/입금완료/정산완료 외는 대시보드에서 숨김
    "계약일",            # YYYY-MM-DD
    "총금액",
    "단가",              # 단위당 가격 (수동 입력)
    "결제방법",          # 세금계산서/계산서/카드결제 (계약 단위 단일)
    "정산유형",          # 1회정산/매월정산/분할정산
    "분납회차",          # 분할정산: 2 또는 3 (수동 입력)
    "구독시작일",
    "구독종료일",
    "메모",
    "created_at",
    "updated_at",
]

# 회계 대시보드에 노출할 노션 상태 (이 외는 자동 숨김)
ACTIVE_NOTION_STATES = {"성공", "입금완료", "정산완료"}


def filter_active_contracts(df: pd.DataFrame) -> pd.DataFrame:
    """노션상태가 강등(제안/협상/리드/실패)된 계약을 대시보드 노출에서 제외.
    노션상태가 빈 값인 경우(마이그레이션 전 row)는 backward-compat으로 유지."""
    if df.empty or "노션상태" not in df.columns:
        return df
    keep = ACTIVE_NOTION_STATES | {""}
    mask = df["노션상태"].fillna("").astype(str).str.strip().isin(keep)
    return df[mask]

PAYMENT_COLUMNS = [
    "payment_id",       # P{timestamp}
    "contract_id",      # FK
    "회차",              # 1/2/3 또는 YYYY-MM (월납)
    "청구예정일",
    "발행일",
    "결제방법",          # 회차 단위 — 해외대조약은 세금계산서/대납액 분리
    "입금완료",          # "TRUE"/"FALSE"
    "입금일",
    "금액",              # 세금계산서 발행 금액
    "단가",              # 회차 단위 단가 (해외대조약: 세금계산서/대납액 각각 독립 입력)
    "고객입금액",        # 실제 입금된 금액 (관세·부가세 대납 등으로 발행액과 다를 수 있음)
    "메모",
    "created_at",
]

PAYMENT_METHODS = ["세금계산서", "계산서", "카드결제", "현금영수증", "대납액"]


def _ensure_headers(ws, expected_headers: list[str]) -> None:
    """1행 헤더 자동 셋업. 비어있거나 expected 컬럼 누락 시 덮어씀."""
    try:
        row1 = ws.row_values(1)
    except Exception:
        row1 = []
    # row1이 expected_headers의 모든 컬럼을 앞에서부터 포함하면 OK (뒤 추가 컬럼은 무시)
    if len(row1) >= len(expected_headers) and row1[: len(expected_headers)] == expected_headers:
        return
    ws.update("A1", [expected_headers], value_input_option="USER_ENTERED")


@st.cache_data(ttl=60, show_spinner=False)
def load_contracts() -> pd.DataFrame:
    ws = get_worksheet("Contracts")
    _ensure_headers(ws, CONTRACT_COLUMNS)
    data = ws.get_all_records(expected_headers=CONTRACT_COLUMNS)
    if not data:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)
    df = pd.DataFrame(data)
    # 빈 row 제거 — Sheets에 빈 행이 끼면 get_all_records가 모든 필드가 비어있는 row를
    # 반환해서 UI에 "—, 0원, 0%" 유령 카드가 표시되는 문제 방지.
    # contract_id가 비어있거나 공백이면 유효하지 않은 row로 간주.
    df = df[df["contract_id"].fillna("").astype(str).str.strip() != ""]
    # 노션 sync로 들어왔지만 본문이 모두 빈 row(과거 데이터)도 표시에서 제외 —
    # contract_id는 자동 생성되어 있으나 건명·고객기관·총금액이 모두 비어있으면 유령 카드.
    _name_empty = df["건명"].fillna("").astype(str).str.strip() == ""
    _cust_empty = df["고객기관"].fillna("").astype(str).str.strip() == ""
    _total_empty = pd.to_numeric(df.get("총금액", 0), errors="coerce").fillna(0) == 0
    df = df[~(_name_empty & _cust_empty & _total_empty)]
    df = df.reset_index(drop=True)
    df["총금액"] = pd.to_numeric(df.get("총금액", 0), errors="coerce").fillna(0)
    df["단가"] = pd.to_numeric(df.get("단가", 0), errors="coerce").fillna(0)
    df["결제방법"] = df.get("결제방법", "").astype(str).fillna("")
    df["분납회차"] = pd.to_numeric(df.get("분납회차", ""), errors="coerce")
    for c in ("계약일", "구독시작일", "구독종료일"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_payments() -> pd.DataFrame:
    ws = get_worksheet("Payments")
    _ensure_headers(ws, PAYMENT_COLUMNS)
    data = ws.get_all_records(expected_headers=PAYMENT_COLUMNS)
    if not data:
        return pd.DataFrame(columns=PAYMENT_COLUMNS)
    df = pd.DataFrame(data)
    # 빈 row 제거 — payment_id 또는 contract_id가 비어있으면 유효하지 않은 row.
    df = df[
        (df["payment_id"].fillna("").astype(str).str.strip() != "")
        & (df["contract_id"].fillna("").astype(str).str.strip() != "")
    ]
    df = df.reset_index(drop=True)
    df["금액"] = pd.to_numeric(df.get("금액", 0), errors="coerce").fillna(0)
    df["단가"] = pd.to_numeric(df.get("단가", 0), errors="coerce").fillna(0)
    df["고객입금액"] = pd.to_numeric(df.get("고객입금액", 0), errors="coerce").fillna(0)
    df["입금완료"] = df.get("입금완료", "FALSE").astype(str).str.upper() == "TRUE"
    df["결제방법"] = df.get("결제방법", "").astype(str).fillna("")
    for c in ("청구예정일", "발행일", "입금일"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def effective_paid_amount(payments: pd.DataFrame) -> float:
    """실제 입금된 매출 합. 고객입금액 > 0이면 그 값, 아니면 금액으로 fallback.
    입금완료=True 인 행만 합산. 대납액 row는 매출이 아니므로 제외."""
    if payments.empty:
        return 0.0
    paid = payments[
        payments["입금완료"]
        & (payments["결제방법"].astype(str).str.strip() != "대납액")
    ]
    if paid.empty:
        return 0.0
    effective = paid["고객입금액"].where(paid["고객입금액"] > 0, paid["금액"])
    return float(effective.sum())


def invalidate_cache():
    load_contracts.clear()
    load_payments.clear()


def sheet_diagnostics() -> dict:
    """계약 시트의 실제 연결 대상과 '쓰기→읽기 반영' 여부를 진단 (캐시 우회).

    동기화는 성공(9건 추가/159건 갱신)이라는데 화면·재조회에 반영이 안 될 때,
    ① 앱이 실제로 어떤 스프레드시트/워크시트를 쓰는지, ② 방금 쓴 값이 즉시 다시
    읽히는지(마커 append→read-back), ③ 시트가 실제로 보는 최신 날짜/행수를 확인한다.

    캐시된 load_contracts()가 아니라 워크시트를 직접 조회하므로, 표시(캐시)와
    실제 시트 내용이 다를 때 그 차이도 드러난다.
    """
    from gsheet_client import get_sheet_id, get_worksheet, open_contracts_sheet

    out: dict = {}
    try:
        sid = get_sheet_id()
        out["secret_sheet_id"] = f"{sid[:6]}…{sid[-4:]}" if sid else "(없음)"
        ss = open_contracts_sheet()
        out["spreadsheet_title"] = ss.title
        out["spreadsheet_id"] = f"{ss.id[:6]}…{ss.id[-4:]}"
        ws = get_worksheet("Contracts")
        out["worksheet_title"] = ws.title

        recs = ws.get_all_records(expected_headers=CONTRACT_COLUMNS)
        out["row_count"] = len(recs)

        def _max_date(key: str) -> str:
            vals = [str(r.get(key, "")).strip() for r in recs if str(r.get(key, "")).strip()]
            return max(vals) if vals else "(없음)"

        out["max_계약일"] = _max_date("계약일")
        out["max_구독종료일"] = _max_date("구독종료일")

        # 쓰기→읽기 반영 테스트: 마커 1행 append 후 즉시 재조회로 확인, 성공 시 정리.
        marker = f"__DIAG_{int(time.time() * 1000)}"
        row = [marker] + [""] * (len(CONTRACT_COLUMNS) - 1)
        ws.append_row(row, value_input_option="RAW")
        recs2 = ws.get_all_records(expected_headers=CONTRACT_COLUMNS)
        out["row_count_after_append"] = len(recs2)
        found_idx = next(
            (i for i, r in enumerate(recs2) if str(r.get("contract_id", "")) == marker),
            None,
        )
        out["write_readback_ok"] = found_idx is not None
        # 마커 정리 (append로 늘어난 행 제거)
        if found_idx is not None:
            try:
                ws.delete_rows(found_idx + 2)
            except Exception as e:  # noqa: BLE001
                out["cleanup_error"] = str(e)[:150]
    except Exception as e:  # noqa: BLE001 — 진단이므로 원문 노출
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    return out


def is_overseas(service_name) -> bool:
    """서비스명이 해외 대조약 케이스인지 판정.
    해외대조약은 고객 실입금액이 발행액과 다를 수 있어 (관세·부가세 등)
    수기 입력이 필요. 그 외는 발행액 = 입금액으로 자동 채움.
    """
    if service_name is None or (isinstance(service_name, float) and pd.isna(service_name)):
        return False
    return "해외대조약" in str(service_name)


def _parse_분납회차(value) -> int:
    """Notion select 값('1회'/'3회'/'12회') 또는 숫자 → int. 없으면 0."""
    if value in (None, "", 0):
        return 0
    s = str(value).strip().replace("회", "").strip()
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def sync_from_notion(notion_df: pd.DataFrame) -> tuple[int, int]:
    """Notion에서 성사 상태 건 중 Sheets에 없는 건 자동 추가.
    Notion `분납회차` 값(예: '12회')을 읽어 Streamlit 분납회차에 저장하고
    동일 회차 수만큼 결제 row를 자동 생성.

    Returns: (추가된 계약 건수, 추가된 결제 회차 건수)
    """
    contracts = load_contracts()
    existing_notion_ids = (
        set(contracts["notion_id"].astype(str)) if not contracts.empty else set()
    )

    target = notion_df[notion_df["상태"].isin(CONFIRMED_STATES)].copy()
    new_contracts = []
    now = pd.Timestamp.now()
    # contract_id → (분납회차 int, 총금액 float, 발행일 str)
    contract_payment_plan = {}

    for _, n in target.iterrows():
        nid = str(n["id"])
        if nid in existing_notion_ids:
            continue
        # 빈 노션 페이지 skip — Name·고객기관·총매출이 모두 비어있으면 의미 없는 row.
        # 이걸 sync하면 시트에 contract_id만 있는 유령 카드가 생성됨.
        _name = str(n.get("name") or "").strip()
        _customer = str(n.get("고객기관") or "").strip()
        _total = float(n.get("총매출") or 0)
        if not _name and not _customer and _total == 0:
            continue
        cid = f"C{int(time.time() * 1000)}{len(new_contracts):03d}"
        분납_int = _parse_분납회차(n.get("분납회차"))
        total = float(n.get("총매출") or 0)
        contract_row = {
            "contract_id": cid,
            "notion_id": nid,
            "고객기관": n.get("고객기관") or "",
            "건명": n.get("name") or "",
            "서비스명": ", ".join(n["서비스명"]) if n.get("서비스명") else "",
            "신규갱신": n.get("신규갱신") or "",
            "노션상태": n.get("상태") or "",
            "계약일": (
                n["계약일"].strftime("%Y-%m-%d")
                if pd.notna(n.get("계약일")) else ""
            ),
            "총금액": total,
            "단가": "",  # 수동 입력 — 신규 동기화 시 빈 셀
            "결제방법": "",  # 수동 선택 — 신규 동기화 시 빈 셀
            "정산유형": n.get("정산유형") or "",
            "분납회차": 분납_int if 분납_int > 0 else "",
            # 노션 계약일(date range)의 start → 구독시작일, end → 구독종료일
            "구독시작일": (
                n["계약일"].strftime("%Y-%m-%d")
                if pd.notna(n.get("계약일")) else ""
            ),
            "구독종료일": (
                n["계약종료일"].strftime("%Y-%m-%d")
                if pd.notna(n.get("계약종료일")) else ""
            ),
            "메모": "",
            "created_at": now.strftime("%Y-%m-%d %H:%M"),
            "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        }
        new_contracts.append(contract_row)
        contract_payment_plan[cid] = {
            "분납": 분납_int,
            "총금액": total,
            "해외": is_overseas(contract_row["서비스명"]),
            # 발행일/입금완료/입금일은 노션과 분리 — 회계 대시보드에서만 관리
        }

    if new_contracts:
        ws_c = get_worksheet("Contracts")
        ws_c.append_rows(
            [[c.get(col, "") for col in CONTRACT_COLUMNS] for c in new_contracts],
            value_input_option="USER_ENTERED",
        )

    # 결제 회차 생성:
    #  - 일반 계약: 분납회차 N → N개 row
    #  - 해외대조약: 분납회차 N → 2N개 row (각 회차마다 세금계산서 + 대납액 페어)
    # 발행일/입금완료/입금일/고객입금액은 시트에 빈 셀로 생성, 대시보드에서 직접 입력
    new_payments_total = 0
    if new_contracts:
        ws_p = get_worksheet("Payments")
        payment_rows = []
        for cid, plan in contract_payment_plan.items():
            n_rounds = plan["분납"] if plan["분납"] > 0 else 1  # 미지정 시 기본 1회
            per_amount = plan["총금액"] / n_rounds if n_rounds > 0 else plan["총금액"]
            overseas = plan["해외"]

            # 일반: N 세금계산서 / 해외대조약: N 세금계산서 + 1 대납액 = N+1 rows
            # 단가는 회차 단위 — 사용자가 수기 입력 (해외대조약 세금계산서/대납액 독립)
            for i in range(1, n_rounds + 1):
                pid = f"P{int(time.time() * 1000)}{len(payment_rows):03d}"
                method = "세금계산서" if overseas else ""
                payment_rows.append({
                    "payment_id": pid,
                    "contract_id": cid,
                    "회차": str(i),
                    "청구예정일": "",
                    "발행일": "",
                    "결제방법": method,
                    "입금완료": "FALSE",
                    "입금일": "",
                    "금액": per_amount,
                    "단가": "",  # 회차 단위 수기 입력
                    "고객입금액": "",  # 실제 입금 확인 후 수기 입력
                    "메모": "Notion 동기화 자동 생성" if i == 1 else f"{n_rounds}회 분납 자동 생성",
                    "created_at": now.strftime("%Y-%m-%d %H:%M"),
                })
            # 해외대조약 — 대납액 1개 row 추가 (계약당 1번)
            if overseas:
                pid = f"P{int(time.time() * 1000)}{len(payment_rows):03d}"
                payment_rows.append({
                    "payment_id": pid,
                    "contract_id": cid,
                    "회차": str(n_rounds + 1),
                    "청구예정일": "",
                    "발행일": "",
                    "결제방법": "대납액",
                    "입금완료": "FALSE",
                    "입금일": "",
                    "금액": "",  # 실제 대납액 확인 후 수기 입력
                    "단가": "",  # 대납 단가 수기 입력 (세금계산서 단가와 독립)
                    "고객입금액": "",
                    "메모": "해외대조약 대납액 (수기 입력)",
                    "created_at": now.strftime("%Y-%m-%d %H:%M"),
                })
        if payment_rows:
            ws_p.append_rows(
                [[p.get(col, "") for col in PAYMENT_COLUMNS] for p in payment_rows],
                value_input_option="USER_ENTERED",
            )
            new_payments_total = len(payment_rows)

    invalidate_cache()
    return len(new_contracts), new_payments_total


def find_orphan_contracts(notion_df: pd.DataFrame) -> pd.DataFrame:
    """시트 contracts 중 노션 confirmed에 없는 row 식별.

    포함 대상:
    - notion_id가 있는데 노션엔 그 page가 없는 경우 (삭제됨)
    - notion_id가 있는데 노션 page 상태가 confirmed(성공/입금완료/정산완료)가 아닌 경우

    notion_id가 빈 row(수동 입력 가능성)는 건드리지 않음.
    """
    contracts = load_contracts()
    if contracts.empty:
        return pd.DataFrame()
    confirmed_notion_ids = set(
        notion_df[notion_df["상태"].isin(CONFIRMED_STATES)]["id"].astype(str)
    )
    has_nid = contracts["notion_id"].fillna("").astype(str).str.strip() != ""
    in_confirmed = contracts["notion_id"].astype(str).isin(confirmed_notion_ids)
    return contracts[has_nid & ~in_confirmed].copy()


def delete_contracts_by_ids(contract_ids: list[str]) -> tuple[int, int]:
    """contracts + 관련 payments 시트 row 삭제.

    Returns: (계약 row 삭제 수, 결제 row 삭제 수)
    """
    if not contract_ids:
        return 0, 0
    target = set(str(x) for x in contract_ids)

    ws_c = get_worksheet("Contracts")
    contracts_all = ws_c.get_all_records(expected_headers=CONTRACT_COLUMNS)
    # 시트 행 번호 (header가 row 1이라 records[i] → sheet row i+2)
    rows_c = [i + 2 for i, r in enumerate(contracts_all) if str(r.get("contract_id", "")) in target]

    ws_p = get_worksheet("Payments")
    payments_all = ws_p.get_all_records(expected_headers=PAYMENT_COLUMNS)
    rows_p = [i + 2 for i, r in enumerate(payments_all) if str(r.get("contract_id", "")) in target]

    # 역순으로 삭제 — 위에서부터 지우면 이후 인덱스가 밀려서 잘못 지움
    for row in sorted(rows_p, reverse=True):
        ws_p.delete_rows(row)
    for row in sorted(rows_c, reverse=True):
        ws_c.delete_rows(row)

    invalidate_cache()
    return len(rows_c), len(rows_p)


def add_payment(contract_id: str, 회차, 청구예정일, 발행일, 금액, 메모: str = "") -> None:
    """결제 회차 수동 추가."""
    pid = f"P{int(time.time() * 1000)}"
    now = pd.Timestamp.now()
    row = {
        "payment_id": pid,
        "contract_id": contract_id,
        "회차": str(회차),
        "청구예정일": 청구예정일.strftime("%Y-%m-%d") if 청구예정일 else "",
        "발행일": 발행일.strftime("%Y-%m-%d") if 발행일 else "",
        "입금완료": "FALSE",
        "입금일": "",
        "금액": float(금액 or 0),
        "메모": 메모,
        "created_at": now.strftime("%Y-%m-%d %H:%M"),
    }
    ws = get_worksheet("Payments")
    ws.append_row([row.get(c, "") for c in PAYMENT_COLUMNS], value_input_option="USER_ENTERED")
    invalidate_cache()


def update_payment_paid(payment_id: str, paid: bool, 입금일=None) -> None:
    """결제 회차 입금완료 토글."""
    ws = get_worksheet("Payments")
    records = ws.get_all_records(expected_headers=PAYMENT_COLUMNS)
    for i, r in enumerate(records):
        if r["payment_id"] == payment_id:
            row_idx = i + 2  # 1-indexed + header
            col_paid = PAYMENT_COLUMNS.index("입금완료") + 1
            col_paid_date = PAYMENT_COLUMNS.index("입금일") + 1
            ws.update_cell(row_idx, col_paid, "TRUE" if paid else "FALSE")
            if paid and 입금일:
                ws.update_cell(row_idx, col_paid_date, 입금일.strftime("%Y-%m-%d"))
            elif not paid:
                ws.update_cell(row_idx, col_paid_date, "")
            invalidate_cache()
            return
    raise ValueError(f"payment_id {payment_id} 못 찾음")


def update_payment_fields(payment_id: str, **fields) -> None:
    """결제 회차 여러 필드 일괄 수정.
    `입금일`이 들어가면 자동으로 `입금완료=TRUE`, 비워지면 `입금완료=FALSE`로 변경.
    """
    if "입금일" in fields:
        v = fields["입금일"]
        has_date = v not in (None, "", pd.NaT) and not (hasattr(v, "__class__") and pd.isna(v))
        fields["입금완료"] = "TRUE" if has_date else "FALSE"

    ws = get_worksheet("Payments")
    records = ws.get_all_records(expected_headers=PAYMENT_COLUMNS)
    for i, r in enumerate(records):
        if r["payment_id"] == payment_id:
            row_idx = i + 2
            for k, v in fields.items():
                if k not in PAYMENT_COLUMNS:
                    continue
                col_idx = PAYMENT_COLUMNS.index(k) + 1
                if v in (None, "", pd.NaT) or (hasattr(v, "__class__") and pd.isna(v)):
                    val = ""
                elif hasattr(v, "strftime"):
                    val = v.strftime("%Y-%m-%d")
                else:
                    val = str(v)
                ws.update_cell(row_idx, col_idx, val)
            invalidate_cache()
            return
    raise ValueError(f"payment_id {payment_id} 못 찾음")


def resync_meta_from_notion(notion_df: pd.DataFrame) -> int:
    """기존 Sheets 계약의 메타 필드를 Notion 최신 값으로 batch 갱신.
    대상: 고객기관·건명·서비스명·신규갱신·정산유형·계약일·총금액
    (분납회차는 resync_installments_from_notion에서 별도 처리)

    Returns: 1개 이상 필드가 갱신된 계약 수
    """
    contracts = load_contracts()
    if contracts.empty:
        return 0
    notion_by_id = {str(r["id"]): r for _, r in notion_df.iterrows()}
    now = pd.Timestamp.now()

    ws_c = get_worksheet("Contracts")
    contract_records = ws_c.get_all_records(expected_headers=CONTRACT_COLUMNS)
    cid_to_row = {r["contract_id"]: i + 2 for i, r in enumerate(contract_records)}

    from gspread.utils import rowcol_to_a1

    # sheet 컬럼 → (notion 필드 키, 변환 함수)
    SYNC_FIELDS = {
        "고객기관": ("고객기관", lambda v: (v or "").strip()),
        "건명": ("name", lambda v: (v or "").strip()),
        "서비스명": ("서비스명", lambda v: ", ".join(v) if v else ""),
        "신규갱신": ("신규갱신", lambda v: v or ""),
        "노션상태": ("상태", lambda v: (v or "").strip()),
        "정산유형": ("정산유형", lambda v: v or ""),
        "계약일": ("계약일", lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) else ""),
        "총금액": ("총매출", lambda v: float(v or 0)),
        # 노션 계약일(date range)의 start/end → 구독시작/종료일
        "구독시작일": ("계약일", lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) else ""),
        "구독종료일": ("계약종료일", lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) else ""),
    }

    batch = []
    updated = 0

    for _, c in contracts.iterrows():
        nid = str(c["notion_id"])
        if nid not in notion_by_id:
            continue
        n = notion_by_id[nid]
        cid = c["contract_id"]
        if cid not in cid_to_row:
            continue
        row_idx = cid_to_row[cid]

        changed = False
        for sheet_col, (notion_key, transform) in SYNC_FIELDS.items():
            new_val = transform(n.get(notion_key))
            old_val = c.get(sheet_col)

            # 숫자(총금액) 비교
            if sheet_col == "총금액":
                old_num = float(old_val) if pd.notna(old_val) and old_val != "" else 0
                new_num = float(new_val)
                if abs(old_num - new_num) < 0.01:
                    continue
                batch.append({
                    "range": rowcol_to_a1(row_idx, CONTRACT_COLUMNS.index(sheet_col) + 1),
                    "values": [[new_num]],
                })
                changed = True
            else:
                old_str = "" if pd.isna(old_val) or old_val in (None,) else str(old_val).strip()
                new_str = str(new_val).strip()
                if old_str == new_str:
                    continue
                batch.append({
                    "range": rowcol_to_a1(row_idx, CONTRACT_COLUMNS.index(sheet_col) + 1),
                    "values": [[new_str]],
                })
                changed = True

        if changed:
            updated += 1
            batch.append({
                "range": rowcol_to_a1(row_idx, CONTRACT_COLUMNS.index("updated_at") + 1),
                "values": [[now.strftime("%Y-%m-%d %H:%M")]],
            })

    if batch:
        ws_c.batch_update(batch, value_input_option="USER_ENTERED")
        invalidate_cache()
    return updated


def resync_installments_from_notion(notion_df: pd.DataFrame) -> tuple[int, int]:
    """기존 Sheets 계약들 중 Notion `분납회차` 값과 다른 건 batch로 일괄 갱신.
    API 호출을 최소화: contracts/payments 각 1번 읽고, 변경분은 batch_update로.

    Returns: (분납회차 갱신된 계약 수, 추가된 결제 회차 row 수)
    """
    contracts = load_contracts()
    if contracts.empty:
        return 0, 0
    payments = load_payments()
    notion_by_id = {str(r["id"]): r for _, r in notion_df.iterrows()}
    now = pd.Timestamp.now()

    # Contracts 워크시트 batch update 준비
    ws_c = get_worksheet("Contracts")
    # 캐시된 contracts DF의 index를 row 매핑으로 사용 (1행은 헤더라 +2)
    # → API read 1회 절약. invalidate_cache 직후 호출이라 정합성 OK.
    cid_to_row = {
        row["contract_id"]: i + 2
        for i, (_, row) in enumerate(contracts.iterrows())
    }

    contract_batch = []  # [{range, values}]
    payments_to_add = []  # [[row]]
    updated_contracts = 0
    added_rows = 0
    col_분납 = CONTRACT_COLUMNS.index("분납회차") + 1
    col_upd = CONTRACT_COLUMNS.index("updated_at") + 1

    from gspread.utils import rowcol_to_a1

    for _, c in contracts.iterrows():
        nid = str(c["notion_id"])
        if nid not in notion_by_id:
            continue
        n = notion_by_id[nid]
        notion_분납 = _parse_분납회차(n.get("분납회차"))
        sheet_분납 = int(c["분납회차"]) if pd.notna(c["분납회차"]) and c["분납회차"] != "" else 0
        if notion_분납 <= 0 or notion_분납 == sheet_분납:
            continue

        cid = c["contract_id"]
        if cid not in cid_to_row:
            continue
        row_idx = cid_to_row[cid]

        # contract 분납회차·updated_at 일괄 업데이트
        contract_batch.append({
            "range": rowcol_to_a1(row_idx, col_분납),
            "values": [[str(notion_분납)]],
        })
        contract_batch.append({
            "range": rowcol_to_a1(row_idx, col_upd),
            "values": [[now.strftime("%Y-%m-%d %H:%M")]],
        })
        updated_contracts += 1

        # 부족한 회차 row 메모리 상에서 계산 (payments DF 활용 — 추가 read 안 함)
        existing = payments[payments["contract_id"] == cid] if not payments.empty else pd.DataFrame()
        existing_rounds = set(existing["회차"].astype(str)) if not existing.empty else set()
        total_amount = float(c["총금액"] or 0)
        per_amount = total_amount / notion_분납 if notion_분납 > 0 else 0
        overseas = is_overseas(c.get("서비스명"))
        # 일반: N rows / 해외대조약: N 세금계산서 + 1 대납액 = N+1 rows
        # 고객입금액은 자동 입력 금지 — 실제 입금 확인 후 사용자가 수기 입력
        for i in range(1, notion_분납 + 1):
            if str(i) in existing_rounds:
                continue
            pid = f"P{int(time.time() * 1000)}{len(payments_to_add):03d}"
            method = "세금계산서" if overseas else ""
            # PAYMENT_COLUMNS 순서: payment_id, contract_id, 회차, 청구예정일, 발행일,
            #   결제방법, 입금완료, 입금일, 금액, 단가, 고객입금액, 메모, created_at
            payments_to_add.append([
                pid, cid, str(i), "", "", method, "FALSE", "", per_amount, "", "",
                f"분납 {notion_분납}회차 자동 생성",
                now.strftime("%Y-%m-%d %H:%M"),
            ])
        if overseas:
            # 대납액 row — 계약당 1개만 (마지막 회차 우측)
            대납_round = str(notion_분납 + 1)
            if 대납_round not in existing_rounds:
                pid = f"P{int(time.time() * 1000)}{len(payments_to_add):03d}"
                payments_to_add.append([
                    pid, cid, 대납_round, "", "", "대납액", "FALSE", "", "", "", "",
                    "해외대조약 대납액 (수기 입력)",
                    now.strftime("%Y-%m-%d %H:%M"),
                ])
        # 기존 회차 중 금액이 총금액과 같은 분납 누락 케이스를 per_amount로 보정
        # (수동 편집 보호 — 총금액 그대로인 경우에만 보정)
        if notion_분납 >= 2 and not existing.empty and total_amount > 0:
            col_금액 = PAYMENT_COLUMNS.index("금액") + 1
            for _, ex_row in existing.iterrows():
                ex_금액 = float(pd.to_numeric(ex_row.get("금액", 0), errors="coerce") or 0)
                if abs(ex_금액 - total_amount) < 1:
                    pid_lookup = ex_row["payment_id"]
                    # payments DF의 시트 row index 찾기
                    payment_records = payments  # already loaded
                    sheet_row_idx = payment_records.index[
                        payment_records["payment_id"] == pid_lookup
                    ].tolist()
                    if sheet_row_idx:
                        row_idx = sheet_row_idx[0] + 2
                        contract_batch.append({
                            "range": rowcol_to_a1(row_idx, col_금액),
                            "values": [[per_amount]],
                        })

    # API 호출 모음: contracts batch_update + payments append (각 1 call)
    if contract_batch:
        ws_c.batch_update(contract_batch, value_input_option="USER_ENTERED")
    if payments_to_add:
        ws_p = get_worksheet("Payments")
        ws_p.append_rows(payments_to_add, value_input_option="USER_ENTERED")
        added_rows = len(payments_to_add)

    invalidate_cache()
    return updated_contracts, added_rows


def ensure_payment_rows(contract_id: str, target_count: int, total_amount: float) -> int:
    """분납 회차가 target_count개 다 있도록 부족분 자동 생성.
    예: target_count=3이면 1·2·3 회차 row 보장. 이미 1회차만 있으면 2·3 추가.
    금액은 총금액/회차로 균등 분할 (수동 조정 가능).
    고객입금액은 자동 입력 금지 — 실제 입금 확인 후 사용자가 수기 입력.

    Returns: 추가된 row 수.
    """
    payments = load_payments()
    existing = payments[payments["contract_id"] == contract_id]
    existing_rounds = set(existing["회차"].astype(str)) if not existing.empty else set()

    # 해외대조약 여부 확인
    contracts = load_contracts()
    contract_row = contracts[contracts["contract_id"] == contract_id]
    overseas = (
        is_overseas(contract_row.iloc[0]["서비스명"])
        if not contract_row.empty else False
    )

    per_amount = float(total_amount or 0) / target_count if target_count > 0 else 0
    now = pd.Timestamp.now()
    new_rows = []
    # 일반: N rows / 해외대조약: N 세금계산서 + 1 대납액 = N+1 rows
    for i in range(1, target_count + 1):
        if str(i) in existing_rounds:
            continue
        pid = f"P{int(time.time() * 1000)}{len(new_rows):03d}"
        method = "세금계산서" if overseas else ""
        new_rows.append({
            "payment_id": pid,
            "contract_id": contract_id,
            "회차": str(i),
            "청구예정일": "",
            "발행일": "",
            "결제방법": method,
            "입금완료": "FALSE",
            "입금일": "",
            "금액": per_amount,
            "단가": "",  # 회차 단위 수기 입력
            "고객입금액": "",
            "메모": f"분납 {target_count}회차 자동 생성",
            "created_at": now.strftime("%Y-%m-%d %H:%M"),
        })
    if overseas:
        # 대납액 row — 계약당 1개만
        대납_round = str(target_count + 1)
        if 대납_round not in existing_rounds:
            pid = f"P{int(time.time() * 1000)}{len(new_rows):03d}"
            new_rows.append({
                "payment_id": pid,
                "contract_id": contract_id,
                "회차": 대납_round,
                "청구예정일": "",
                "발행일": "",
                "결제방법": "대납액",
                "입금완료": "FALSE",
                "입금일": "",
                "금액": "",
                "단가": "",  # 대납 단가 수기 입력 (세금계산서 단가와 독립)
                "고객입금액": "",
                "메모": "해외대조약 대납액 (수기 입력)",
                "created_at": now.strftime("%Y-%m-%d %H:%M"),
            })

    if new_rows:
        ws = get_worksheet("Payments")
        ws.append_rows(
            [[r.get(c, "") for c in PAYMENT_COLUMNS] for r in new_rows],
            value_input_option="USER_ENTERED",
        )

    # 분납회차 >= 2 이고 기존 회차 금액이 총금액과 동일(= 분납 누락 상태)이면 per_amount로 보정
    # 고객입금액은 건드리지 않음 — 실제 입금 확인 후 수기 입력 정책
    if target_count >= 2 and not existing.empty and total_amount > 0:
        for _, ex_row in existing.iterrows():
            ex_금액 = float(pd.to_numeric(ex_row.get("금액", 0), errors="coerce") or 0)
            if abs(ex_금액 - total_amount) < 1:
                update_payment_fields(ex_row["payment_id"], 금액=per_amount)

    if new_rows or target_count >= 2:
        invalidate_cache()
    return len(new_rows)


def delete_contract(contract_id: str) -> dict:
    """계약 + 연결된 모든 결제 회차를 시트에서 영구 삭제.
    매칭된 카드결제가 있으면 매칭_상태를 '미매칭'으로 되돌려서 빠진 row 추적 가능.

    Returns: {"contract": 0/1, "payments": N, "cards_unmatched": M}
    """
    result = {"contract": 0, "payments": 0, "cards_unmatched": 0}

    ws_p = get_worksheet("Payments")
    payment_records = ws_p.get_all_records(expected_headers=PAYMENT_COLUMNS)
    target_pids = {
        r["payment_id"] for r in payment_records if r["contract_id"] == contract_id
    }

    # 1) 카드결제 매칭 해제 (CardPayments 시트가 있을 때만)
    if target_pids:
        try:
            ws_card = get_worksheet("CardPayments")
            CARD_COLS_LOCAL = [
                "card_id", "pg", "결제일", "정산일", "거래금액", "수수료", "정산금액",
                "카드사", "승인번호", "거래번호", "구매자", "상품명", "상태",
                "매칭_payment_id", "매칭_상태", "업로드일시", "메모",
            ]
            col_cpid = CARD_COLS_LOCAL.index("매칭_payment_id") + 1
            col_cst = CARD_COLS_LOCAL.index("매칭_상태") + 1
            for i, c_rec in enumerate(ws_card.get_all_records()):
                if str(c_rec.get("매칭_payment_id", "")).strip() in target_pids:
                    sheet_row = i + 2
                    ws_card.update_cell(sheet_row, col_cpid, "")
                    ws_card.update_cell(sheet_row, col_cst, "미매칭")
                    result["cards_unmatched"] += 1
        except Exception:
            pass  # CardPayments 탭 없을 수도 있음

    # 2) Payments row 삭제 (역순으로 — 위에서부터 지우면 index가 shift됨)
    payment_rows = [
        i + 2 for i, r in enumerate(payment_records) if r["contract_id"] == contract_id
    ]
    for row_idx in sorted(payment_rows, reverse=True):
        ws_p.delete_rows(row_idx)
        result["payments"] += 1

    # 3) Contracts row 삭제
    ws_c = get_worksheet("Contracts")
    for i, r in enumerate(ws_c.get_all_records(expected_headers=CONTRACT_COLUMNS)):
        if r["contract_id"] == contract_id:
            ws_c.delete_rows(i + 2)
            result["contract"] = 1
            break

    invalidate_cache()
    return result


def create_contract_from_card(card_row) -> str:
    """카드결제 row 기반으로 노션 미관리 신규 계약 + 결제 1회차 자동 생성.
    Returns: 생성된 payment_id (매칭 대상)."""
    cid = f"C{int(time.time() * 1000)}"
    pid = f"P{int(time.time() * 1000)}"
    now = pd.Timestamp.now()
    paid = pd.to_datetime(card_row.get("결제일"), errors="coerce")
    settle = pd.to_datetime(card_row.get("정산일"), errors="coerce")
    amount = int(pd.to_numeric(card_row.get("거래금액"), errors="coerce") or 0)
    buyer = str(card_row.get("구매자") or "").strip() or "(미지정)"
    product = str(card_row.get("상품명") or "").strip()

    contract_row = {
        "contract_id": cid,
        "notion_id": "",
        "고객기관": buyer,
        "건명": buyer,
        "서비스명": product,
        "신규갱신": "신규",
        "노션상태": "성공",
        "계약일": paid.strftime("%Y-%m-%d") if pd.notna(paid) else "",
        "총금액": amount,
        "단가": "",
        "결제방법": "카드결제",
        "정산유형": "1회정산",
        "분납회차": 1,
        "구독시작일": paid.strftime("%Y-%m-%d") if pd.notna(paid) else "",
        "구독종료일": "",
        "메모": "카드결제 자동 생성 (노션 미관리)",
        "created_at": now.strftime("%Y-%m-%d %H:%M"),
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
    }
    payment_row = {
        "payment_id": pid,
        "contract_id": cid,
        "회차": "1",
        "청구예정일": paid.strftime("%Y-%m-%d") if pd.notna(paid) else "",
        "발행일": paid.strftime("%Y-%m-%d") if pd.notna(paid) else "",
        "결제방법": "카드결제",
        "입금완료": "TRUE" if pd.notna(settle) else "FALSE",
        "입금일": settle.strftime("%Y-%m-%d") if pd.notna(settle) else "",
        "금액": amount,
        "단가": "",
        "고객입금액": amount,
        "메모": "카드결제 자동 생성",
        "created_at": now.strftime("%Y-%m-%d %H:%M"),
    }

    ws_c = get_worksheet("Contracts")
    ws_p = get_worksheet("Payments")
    ws_c.append_row(
        [contract_row.get(c, "") for c in CONTRACT_COLUMNS],
        value_input_option="USER_ENTERED",
    )
    ws_p.append_row(
        [payment_row.get(c, "") for c in PAYMENT_COLUMNS],
        value_input_option="USER_ENTERED",
    )
    invalidate_cache()
    return pid


def update_contract_meta(contract_id: str, **fields) -> None:
    """계약 메타데이터(분납회차·구독기간·메모 등) 수정."""
    ws = get_worksheet("Contracts")
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r["contract_id"] == contract_id:
            row_idx = i + 2
            for k, v in fields.items():
                if k in CONTRACT_COLUMNS:
                    col = CONTRACT_COLUMNS.index(k) + 1
                    val = v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else (str(v) if v is not None else "")
                    ws.update_cell(row_idx, col, val)
            # updated_at 갱신
            col_upd = CONTRACT_COLUMNS.index("updated_at") + 1
            ws.update_cell(row_idx, col_upd, pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            invalidate_cache()
            return
    raise ValueError(f"contract_id {contract_id} 못 찾음")
