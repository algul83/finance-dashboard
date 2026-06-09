"""카드결제 정산내역 (이노페이/토스) 파싱 + Payments 회차 자동 매칭.

이노페이 정산내역은 `.xls` 확장자지만 실제로는 HTML 테이블 → pandas.read_html.
"""
from __future__ import annotations

import time
from difflib import SequenceMatcher
from io import BytesIO, StringIO
from typing import Optional

import pandas as pd
import streamlit as st

from gsheet_client import get_worksheet

CARD_COLUMNS = [
    "card_id", "pg", "결제일", "정산일", "거래금액", "수수료", "정산금액",
    "카드사", "승인번호", "거래번호", "구매자", "상품명", "상태",
    "매칭_payment_id", "매칭_상태", "업로드일시", "메모",
]

# 매칭 임계값
NAME_SIM_THRESHOLD = 0.75   # 고객명 fuzzy ratio
DATE_WINDOW_DAYS = 14       # 청구예정일/발행일 ±이내


def _ensure_headers(ws, expected: list[str]) -> None:
    try:
        row1 = ws.row_values(1)
    except Exception:
        row1 = []
    if len(row1) >= len(expected) and row1[: len(expected)] == expected:
        return
    ws.update("A1", [expected], value_input_option="USER_ENTERED")


@st.cache_data(ttl=60, show_spinner=False)
def load_card_payments() -> pd.DataFrame:
    ws = get_worksheet("CardPayments")
    _ensure_headers(ws, CARD_COLUMNS)
    data = ws.get_all_records(expected_headers=CARD_COLUMNS)
    if not data:
        return pd.DataFrame(columns=CARD_COLUMNS)
    df = pd.DataFrame(data)
    df["거래금액"] = pd.to_numeric(df.get("거래금액", 0), errors="coerce").fillna(0)
    df["수수료"] = pd.to_numeric(df.get("수수료", 0), errors="coerce").fillna(0)
    df["정산금액"] = pd.to_numeric(df.get("정산금액", 0), errors="coerce").fillna(0)
    for c in ("결제일", "정산일"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def invalidate_cache():
    load_card_payments.clear()


def parse_innopay(file) -> pd.DataFrame:
    """이노페이 정산내역 → 정규화된 DataFrame.

    형식 자동 감지:
      - 진짜 xlsx (PK ZIP header) → pd.read_excel
      - HTML 위장 .xls → pd.read_html (utf-8 / cp949 / euc-kr 인코딩 순차 시도)
    원본 컬럼: 결제서비스명·정산일·승인일·상호·MID·거래금액·수수료·VAT·
              ...·정산금액·카드·승인번호·주문번호·구매자·상품명·TID·상태
    → CardPayments 스키마로 변환.
    """
    if hasattr(file, "read"):
        content = file.read()
        if hasattr(file, "seek"):
            file.seek(0)
    else:
        with open(file, "rb") as fh:
            content = fh.read()

    if content[:4] == b"PK\x03\x04":
        # 진짜 xlsx (ZIP container)
        tables = [pd.read_excel(BytesIO(content))]
    else:
        # HTML 텍스트 — 인코딩 추정
        text = None
        for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("파일 인코딩을 인식하지 못했습니다.")
        tables = pd.read_html(StringIO(text))

    if not tables:
        raise ValueError("엑셀에서 테이블을 찾지 못했습니다.")
    raw = tables[0]
    if raw.empty:
        return pd.DataFrame(columns=CARD_COLUMNS)

    # 컬럼명에 공백 들어가있는 케이스 정규화 ('V A T' → 'VAT' 등)
    raw.columns = [str(c).replace(" ", "") for c in raw.columns]

    out = pd.DataFrame()
    out["pg"] = ["이노페이"] * len(raw)
    out["결제일"] = pd.to_datetime(raw.get("승인일"), errors="coerce")
    out["정산일"] = pd.to_datetime(raw.get("정산일"), errors="coerce")
    out["거래금액"] = pd.to_numeric(raw.get("거래금액", 0), errors="coerce").fillna(0).astype(int)
    out["수수료"] = (
        pd.to_numeric(raw.get("수수료", 0), errors="coerce").fillna(0)
        + pd.to_numeric(raw.get("VAT", 0), errors="coerce").fillna(0)
    ).astype(int)
    out["정산금액"] = pd.to_numeric(raw.get("정산금액", 0), errors="coerce").fillna(0).astype(int)
    out["카드사"] = raw.get("카드", "").astype(str).str.strip()
    out["승인번호"] = raw.get("승인번호", "").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    out["거래번호"] = raw.get("주문번호", "").astype(str).str.strip()
    out["구매자"] = raw.get("구매자", "").astype(str).str.strip()
    out["상품명"] = raw.get("상품명", "").astype(str).str.strip()
    out["상태"] = raw.get("상태", "").astype(str).str.strip()
    # 합계/footer row 제외 — 결제일·구매자·상태 중 하나라도 비어있으면 데이터 row 아님
    valid = (
        out["결제일"].notna()
        & (out["구매자"].str.len() > 0)
        & (out["구매자"].str.lower() != "nan")
        & (out["상태"].str.len() > 0)
        & (out["상태"].str.lower() != "nan")
    )
    return out[valid].reset_index(drop=True)


def _name_similarity(a: str, b: str) -> float:
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    # 양쪽 모두 substring으로 포함되면 100% 간주
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def find_match(
    card_row: pd.Series,
    contracts: pd.DataFrame,
    payments: pd.DataFrame,
) -> tuple[Optional[str], str, list[str]]:
    """카드결제 1건에 대해 Payments 회차 매칭.

    Returns: (payment_id or None, 매칭_상태 ['자동'|'다중'|'미매칭'], 후보 payment_id 리스트)
    """
    if card_row["상태"] != "승인" or contracts.empty or payments.empty:
        return None, "미매칭", []

    # 1) Payments 중 결제방법="카드결제" 또는 비어있고 거래금액과 정확 일치
    amount = int(card_row["거래금액"])
    candidates = payments[
        (
            (payments["결제방법"].astype(str).str.strip() == "카드결제")
            | (payments["결제방법"].astype(str).str.strip() == "")
        )
        & (pd.to_numeric(payments["금액"], errors="coerce").fillna(0).astype(int) == amount)
    ].copy()
    if candidates.empty:
        return None, "미매칭", []

    # 2) 구매자명과 고객기관 fuzzy 매칭
    buyer = str(card_row["구매자"] or "").strip()
    paid_date = pd.to_datetime(card_row["결제일"], errors="coerce")

    candidates = candidates.merge(
        contracts[["contract_id", "고객기관"]], on="contract_id", how="left"
    )
    candidates["_name_sim"] = candidates["고객기관"].apply(
        lambda x: _name_similarity(str(x or ""), buyer)
    )
    candidates = candidates[candidates["_name_sim"] >= NAME_SIM_THRESHOLD]
    if candidates.empty:
        return None, "미매칭", []

    # 3) 결제일 ±14일 청구예정일/발행일 매칭 우선순위
    def _date_score(row):
        for col in ("청구예정일", "발행일"):
            d = pd.to_datetime(row.get(col), errors="coerce")
            if pd.notna(d) and pd.notna(paid_date):
                diff = abs((d - paid_date).days)
                if diff <= DATE_WINDOW_DAYS:
                    return diff
        return 999

    candidates["_date_score"] = candidates.apply(_date_score, axis=1)
    # 날짜 후보 우선
    near = candidates[candidates["_date_score"] < 999].sort_values(
        ["_date_score", "_name_sim"], ascending=[True, False]
    )
    pool = near if not near.empty else candidates.sort_values("_name_sim", ascending=False)
    pids = pool["payment_id"].tolist()
    if len(pids) == 1:
        return pids[0], "자동", pids
    return None, "다중", pids


def auto_match_and_save(
    new_cards: pd.DataFrame,
    contracts: pd.DataFrame,
    payments: pd.DataFrame,
) -> dict:
    """파싱된 카드결제 row를 자동 매칭 후 CardPayments 시트에 append.

    반환: {"saved": N, "auto": N, "multi": N, "miss": N}
    """
    if new_cards.empty:
        return {"saved": 0, "auto": 0, "multi": 0, "miss": 0}

    ws = get_worksheet("CardPayments")
    existing = load_card_payments()
    # 거래번호 기준 중복 제외 (이미 업로드된 row)
    existed_keys = set(existing["거래번호"].astype(str)) if not existing.empty else set()

    now = pd.Timestamp.now()
    rows_to_append = []
    counts = {"saved": 0, "auto": 0, "multi": 0, "miss": 0}

    for i, (_, c) in enumerate(new_cards.iterrows()):
        if str(c.get("거래번호", "")) in existed_keys:
            continue
        pid, status, _ = find_match(c, contracts, payments)
        counts[
            {"자동": "auto", "다중": "multi", "미매칭": "miss"}[status]
        ] += 1
        card_id = f"CP{int(time.time() * 1000)}{i:03d}"

        # CardPayments 시트 row (헤더 순서 그대로)
        row = {
            "card_id": card_id,
            "pg": c.get("pg", ""),
            "결제일": c["결제일"].strftime("%Y-%m-%d") if pd.notna(c["결제일"]) else "",
            "정산일": c["정산일"].strftime("%Y-%m-%d") if pd.notna(c["정산일"]) else "",
            "거래금액": int(c["거래금액"]),
            "수수료": int(c["수수료"]),
            "정산금액": int(c["정산금액"]),
            "카드사": c.get("카드사", ""),
            "승인번호": c.get("승인번호", ""),
            "거래번호": c.get("거래번호", ""),
            "구매자": c.get("구매자", ""),
            "상품명": c.get("상품명", ""),
            "상태": c.get("상태", ""),
            "매칭_payment_id": pid or "",
            "매칭_상태": status,
            "업로드일시": now.strftime("%Y-%m-%d %H:%M"),
            "메모": "",
        }
        rows_to_append.append([row.get(col, "") for col in CARD_COLUMNS])
        counts["saved"] += 1

    if rows_to_append:
        ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        invalidate_cache()
    return counts


def set_match(card_id: str, payment_id: str) -> None:
    """수동 매칭 — card_id의 매칭_payment_id + 매칭_상태='수동' 업데이트."""
    ws = get_worksheet("CardPayments")
    records = ws.get_all_records(expected_headers=CARD_COLUMNS)
    for i, r in enumerate(records):
        if r["card_id"] == card_id:
            row_idx = i + 2
            col_pid = CARD_COLUMNS.index("매칭_payment_id") + 1
            col_st = CARD_COLUMNS.index("매칭_상태") + 1
            ws.update_cell(row_idx, col_pid, payment_id)
            ws.update_cell(row_idx, col_st, "수동" if payment_id else "미매칭")
            invalidate_cache()
            return
    raise ValueError(f"card_id {card_id} 못 찾음")
