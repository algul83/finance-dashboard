"""Notion 영업현황 DB → DataFrame 변환."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from notion_client import Client

DATA_SOURCE_ID = "2ab3a733-4743-8132-91a6-000bdac816e9"


def _token() -> str:
    try:
        t = st.secrets.get("NOTION_TOKEN", "")
        if t:
            return t
    except Exception:
        pass
    return os.environ.get("NOTION_TOKEN", "")


def _prop(row: dict, name: str):
    p = row["properties"].get(name, {})
    t = p.get("type")
    if t == "title":
        return "".join(x["plain_text"] for x in p["title"])
    if t == "status":
        return p["status"]["name"] if p["status"] else None
    if t == "select":
        return p["select"]["name"] if p["select"] else None
    if t == "multi_select":
        return [x["name"] for x in p["multi_select"]]
    if t == "checkbox":
        return p["checkbox"]
    if t == "date":
        return p["date"]["start"] if p["date"] else None
    if t == "number":
        return p["number"]
    if t == "rich_text":
        return "".join(x["plain_text"] for x in p["rich_text"])
    return None


@st.cache_data(ttl=600, show_spinner="영업현황 DB 불러오는 중...")
def load_sales_data() -> pd.DataFrame:
    """Notion 영업현황 DB 전체 페이지 → 정규화된 DataFrame."""
    token = _token()
    if not token:
        raise RuntimeError("NOTION_TOKEN이 설정되지 않았습니다 (secrets.toml 또는 환경변수)")

    notion = Client(auth=token)
    rows = []
    cursor = None
    while True:
        kwargs = {"data_source_id": DATA_SOURCE_ID, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.data_sources.query(**kwargs)
        rows.extend(resp["results"])
        cursor = resp.get("next_cursor")
        if not cursor:
            break

    records = []
    for r in rows:
        records.append({
            "id": r["id"],
            "url": r.get("url", ""),
            "name": _prop(r, "Name"),
            "고객기관": _prop(r, "고객 기관"),
            "상태": _prop(r, "상태"),
            "신규갱신": _prop(r, "신규/갱신"),
            "서비스명": _prop(r, "서비스명") or [],
            "정산유형": _prop(r, "정산유형"),
            "총매출": _prop(r, "총 매출금액(부가세포함)") or 0,
            "우선순위": _prop(r, "우선순위"),
            "계약일": _prop(r, "계약일"),
            "세금계산서발행일": _prop(r, "세금계산서 발행 일"),
            "입금완료": _prop(r, "입금완료 여부"),
            "비고": _prop(r, "비고"),
        })

    df = pd.DataFrame(records)
    # 날짜 컬럼 datetime 변환
    for c in ("계약일", "세금계산서발행일"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["입금완료"] = df["입금완료"].fillna(False).astype(bool)
    df["총매출"] = pd.to_numeric(df["총매출"], errors="coerce").fillna(0)
    return df


def explode_services(df: pd.DataFrame) -> pd.DataFrame:
    """서비스명(multi_select) 폭발 → 행별 1서비스."""
    tmp = df.copy()
    tmp["서비스명"] = tmp["서비스명"].apply(lambda x: x if x else ["(없음)"])
    return tmp.explode("서비스명")
