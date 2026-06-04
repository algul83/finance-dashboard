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
    "계약일",            # YYYY-MM-DD
    "총금액",
    "정산유형",          # 1회정산/매월정산/분할정산
    "분납회차",          # 분할정산: 2 또는 3 (수동 입력)
    "구독시작일",
    "구독종료일",
    "메모",
    "created_at",
    "updated_at",
]

PAYMENT_COLUMNS = [
    "payment_id",       # P{timestamp}
    "contract_id",      # FK
    "회차",              # 1/2/3 또는 YYYY-MM (월납)
    "청구예정일",
    "발행일",
    "입금완료",          # "TRUE"/"FALSE"
    "입금일",
    "금액",
    "메모",
    "created_at",
]


def _ensure_headers(ws, expected_headers: list[str]) -> None:
    """1행 헤더 자동 셋업. 비어있거나 첫 컬럼이 다르면 expected_headers로 덮어씀."""
    try:
        row1 = ws.row_values(1)
    except Exception:
        row1 = []
    # 첫 컬럼이 expected[0]과 일치하면 정상으로 간주
    if row1 and row1[0] == expected_headers[0]:
        return
    # 비었거나 첫 컬럼이 다르면 헤더 작성 (기존 데이터가 있으면 행을 밀어내지 않고 1행만 덮어씀)
    ws.update("A1", [expected_headers], value_input_option="USER_ENTERED")


@st.cache_data(ttl=60, show_spinner=False)
def load_contracts() -> pd.DataFrame:
    ws = get_worksheet("Contracts")
    _ensure_headers(ws, CONTRACT_COLUMNS)
    data = ws.get_all_records(expected_headers=CONTRACT_COLUMNS)
    if not data:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)
    df = pd.DataFrame(data)
    df["총금액"] = pd.to_numeric(df.get("총금액", 0), errors="coerce").fillna(0)
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
    df["금액"] = pd.to_numeric(df.get("금액", 0), errors="coerce").fillna(0)
    df["입금완료"] = df.get("입금완료", "FALSE").astype(str).str.upper() == "TRUE"
    for c in ("청구예정일", "발행일", "입금일"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def invalidate_cache():
    load_contracts.clear()
    load_payments.clear()


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
    # contract_id → (분납회차 int, 총금액 float, 발행일 str, 입금완료 bool)
    contract_payment_plan = {}

    for _, n in target.iterrows():
        nid = str(n["id"])
        if nid in existing_notion_ids:
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
            "계약일": (
                n["계약일"].strftime("%Y-%m-%d")
                if pd.notna(n.get("계약일")) else ""
            ),
            "총금액": total,
            "정산유형": n.get("정산유형") or "",
            "분납회차": 분납_int if 분납_int > 0 else "",
            "구독시작일": "",
            "구독종료일": "",
            "메모": "",
            "created_at": now.strftime("%Y-%m-%d %H:%M"),
            "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        }
        new_contracts.append(contract_row)
        contract_payment_plan[cid] = {
            "분납": 분납_int,
            "총금액": total,
            "발행일": (
                n["세금계산서발행일"].strftime("%Y-%m-%d")
                if pd.notna(n.get("세금계산서발행일")) else ""
            ),
            "입금완료": bool(n.get("입금완료")),
        }

    if new_contracts:
        ws_c = get_worksheet("Contracts")
        ws_c.append_rows(
            [[c.get(col, "") for col in CONTRACT_COLUMNS] for c in new_contracts],
            value_input_option="USER_ENTERED",
        )

    # 결제 회차 생성: 분납회차 N → N개 row 모두 생성
    # 1회차에 한해 Notion 발행일/입금완료 값을 복사
    new_payments_total = 0
    if new_contracts:
        ws_p = get_worksheet("Payments")
        payment_rows = []
        for cid, plan in contract_payment_plan.items():
            n_rounds = plan["분납"] if plan["분납"] > 0 else 1  # 미지정 시 기본 1회
            per_amount = plan["총금액"] / n_rounds if n_rounds > 0 else plan["총금액"]
            for i in range(1, n_rounds + 1):
                pid = f"P{int(time.time() * 1000)}{len(payment_rows):03d}"
                is_first = (i == 1)
                payment_rows.append({
                    "payment_id": pid,
                    "contract_id": cid,
                    "회차": str(i),
                    "청구예정일": "",
                    "발행일": plan["발행일"] if is_first else "",
                    "입금완료": "TRUE" if (is_first and plan["입금완료"]) else "FALSE",
                    "입금일": "",
                    "금액": per_amount,
                    "메모": "Notion 동기화 자동 생성" if is_first else f"{n_rounds}회 분납 자동 생성",
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


def resync_installments_from_notion(notion_df: pd.DataFrame) -> tuple[int, int]:
    """기존 Sheets 계약들 중 Notion `분납회차` 값과 다른 건 업데이트 + 회차 row 자동 생성.

    Returns: (분납회차 갱신된 계약 수, 추가된 결제 회차 row 수)
    """
    contracts = load_contracts()
    if contracts.empty:
        return 0, 0
    notion_by_id = {str(r["id"]): r for _, r in notion_df.iterrows()}

    updated_contracts = 0
    added_rows = 0
    for _, c in contracts.iterrows():
        nid = str(c["notion_id"])
        if nid not in notion_by_id:
            continue
        n = notion_by_id[nid]
        notion_분납 = _parse_분납회차(n.get("분납회차"))
        sheet_분납 = int(c["분납회차"]) if pd.notna(c["분납회차"]) and c["분납회차"] != "" else 0

        # 노션 값이 있고 sheet와 다르면 갱신
        if notion_분납 > 0 and notion_분납 != sheet_분납:
            update_contract_meta(c["contract_id"], 분납회차=notion_분납)
            updated_contracts += 1
            # 부족한 회차 자동 추가
            added_rows += ensure_payment_rows(
                c["contract_id"], notion_분납, float(c["총금액"] or 0)
            )

    invalidate_cache()
    return updated_contracts, added_rows


def ensure_payment_rows(contract_id: str, target_count: int, total_amount: float) -> int:
    """분납 회차가 target_count개 다 있도록 부족분 자동 생성.
    예: target_count=3이면 1·2·3 회차 row 보장. 이미 1회차만 있으면 2·3 추가.
    금액은 총금액/회차로 균등 분할 (수동 조정 가능).

    Returns: 추가된 row 수.
    """
    payments = load_payments()
    existing = payments[payments["contract_id"] == contract_id]
    existing_rounds = set(existing["회차"].astype(str)) if not existing.empty else set()

    per_amount = float(total_amount or 0) / target_count if target_count > 0 else 0
    now = pd.Timestamp.now()
    new_rows = []
    for i in range(1, target_count + 1):
        if str(i) in existing_rounds:
            continue
        pid = f"P{int(time.time() * 1000)}{len(new_rows):03d}"
        new_rows.append({
            "payment_id": pid,
            "contract_id": contract_id,
            "회차": str(i),
            "청구예정일": "",
            "발행일": "",
            "입금완료": "FALSE",
            "입금일": "",
            "금액": per_amount,
            "메모": f"분납 {target_count}회차 자동 생성",
            "created_at": now.strftime("%Y-%m-%d %H:%M"),
        })

    if new_rows:
        ws = get_worksheet("Payments")
        ws.append_rows(
            [[r.get(c, "") for c in PAYMENT_COLUMNS] for r in new_rows],
            value_input_option="USER_ENTERED",
        )
        invalidate_cache()
    return len(new_rows)


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
