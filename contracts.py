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


@st.cache_data(ttl=60, show_spinner=False)
def load_contracts() -> pd.DataFrame:
    ws = get_worksheet("Contracts")
    data = ws.get_all_records()
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
    data = ws.get_all_records()
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


def sync_from_notion(notion_df: pd.DataFrame) -> tuple[int, int]:
    """Notion에서 성사 상태 건 중 Sheets에 없는 건 자동 추가.

    Returns: (추가된 계약 건수, 추가된 결제 회차 건수)
    """
    contracts = load_contracts()
    existing_notion_ids = (
        set(contracts["notion_id"].astype(str)) if not contracts.empty else set()
    )

    target = notion_df[notion_df["상태"].isin(CONFIRMED_STATES)].copy()
    new_contracts = []
    new_payments = []
    now = pd.Timestamp.now()

    for _, n in target.iterrows():
        nid = str(n["id"])
        if nid in existing_notion_ids:
            continue
        cid = f"C{int(time.time() * 1000)}{len(new_contracts):03d}"
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
            "총금액": float(n.get("총매출") or 0),
            "정산유형": n.get("정산유형") or "",
            "분납회차": "",
            "구독시작일": "",
            "구독종료일": "",
            "메모": "",
            "created_at": now.strftime("%Y-%m-%d %H:%M"),
            "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        }
        new_contracts.append(contract_row)

        # Notion에 이미 세금계산서 발행일이 있으면 1회차 결제로 자동 등록
        if pd.notna(n.get("세금계산서발행일")):
            pid = f"P{int(time.time() * 1000)}{len(new_payments):03d}"
            new_payments.append({
                "payment_id": pid,
                "contract_id": cid,
                "회차": "1",
                "청구예정일": "",
                "발행일": n["세금계산서발행일"].strftime("%Y-%m-%d"),
                "입금완료": "TRUE" if n.get("입금완료") else "FALSE",
                "입금일": "",
                "금액": float(n.get("총매출") or 0),
                "메모": "Notion 동기화 자동 생성",
                "created_at": now.strftime("%Y-%m-%d %H:%M"),
            })

    if new_contracts:
        ws_c = get_worksheet("Contracts")
        ws_c.append_rows(
            [[c.get(col, "") for col in CONTRACT_COLUMNS] for c in new_contracts],
            value_input_option="USER_ENTERED",
        )
    if new_payments:
        ws_p = get_worksheet("Payments")
        ws_p.append_rows(
            [[p.get(col, "") for col in PAYMENT_COLUMNS] for p in new_payments],
            value_input_option="USER_ENTERED",
        )

    invalidate_cache()
    return len(new_contracts), len(new_payments)


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
    records = ws.get_all_records()
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
