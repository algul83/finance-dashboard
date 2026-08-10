"""Notion 영업현황 DB → DataFrame 변환."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from notion_client import Client

# 여러 연도의 영업현황 페이지를 함께 로드.
# DB 자체가 회계연도 기준으로 분리되어 있어 각 페이지를 모두 읽어서 concat.
DATA_SOURCE_IDS = [
    "2ab3a733-4743-8132-91a6-000bdac816e9",  # 2026년 영업현황
    "1513a733-4743-8196-b228-000b5d509803",  # 2025년 영업현황
    "3c4c23b8-8b39-47cd-9931-41da119d10d2",  # 2024년 영업현황
    "f3eab30f-c809-44c2-b8b5-9f46c2012c09",  # 2023년 영업
]
# 하위호환: 일부 모듈이 단수 상수를 참조할 수 있어 첫 ID로 alias
DATA_SOURCE_ID = DATA_SOURCE_IDS[0]


def _normalize_status(s):
    """2025 페이지는 '성공 💪' 등 이모지 포함 상태값을 사용. 다운스트림 필터와
    호환되도록 이모지·공백 제거하고 정규화."""
    if not s:
        return s
    return s.replace("💪", "").strip()


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


def _prop_date_end(row: dict, name: str):
    """노션 date 속성의 종료일(end)만 추출. 단일 날짜는 None 반환."""
    p = row["properties"].get(name, {})
    if p.get("type") != "date" or not p.get("date"):
        return None
    return p["date"].get("end")


@st.cache_data(ttl=600, show_spinner="영업현황 DB 불러오는 중...")
def load_sales_data() -> pd.DataFrame:
    """Notion 영업현황 DB 전체 페이지 → 정규화된 DataFrame.
    2025·2026 영업현황 모두 로드해 concat. 한쪽에만 있는 필드는 None."""
    token = _token()
    if not token:
        raise RuntimeError("NOTION_TOKEN이 설정되지 않았습니다 (secrets.toml 또는 환경변수)")

    notion = Client(auth=token)
    records = []
    source_errors = []
    for ds_id in DATA_SOURCE_IDS:
        try:
            cursor = None
            while True:
                kwargs = {"data_source_id": ds_id, "page_size": 100}
                if cursor:
                    kwargs["start_cursor"] = cursor
                resp = notion.data_sources.query(**kwargs)
                for r in resp["results"]:
                    records.append({
                        "id": r["id"],
                        "source": ds_id,
                        "url": r.get("url", ""),
                        "name": _prop(r, "Name"),
                        "고객기관": _prop(r, "고객 기관"),
                        "상태": _normalize_status(_prop(r, "상태")),
                        "신규갱신": _prop(r, "신규/갱신"),
                        "서비스명": _prop(r, "서비스명") or [],
                        "정산유형": _prop(r, "정산유형"),
                        "분납회차": _prop(r, "분납회차"),  # select: '1회'/'3회'/'12회'
                        # 2024+: '총 매출금액(부가세포함)', 2023: '매출금액(부가세포함)' (fallback)
                        "총매출": _prop(r, "총 매출금액(부가세포함)") or _prop(r, "매출금액(부가세포함)") or 0,
                        "우선순위": _prop(r, "우선순위"),
                        "계약일": _prop(r, "계약일"),  # date range의 start (계약 시작일)
                        "계약종료일": _prop_date_end(r, "계약일"),  # date range의 end (계약 종료일)
                        "비고": _prop(r, "비고"),
                        # 세금계산서발행일·입금완료여부는 노션과 분리 — 회계대시보드(Sheets)에서만 관리
                    })
                cursor = resp.get("next_cursor")
                if not cursor:
                    break
        except Exception as e:
            # 한 데이터 소스 권한 누락 등으로 실패해도 나머지로 계속 진행
            source_errors.append((ds_id, str(e)[:200]))
            try:
                st.warning(
                    f"⚠️ Notion 데이터 소스 `{ds_id[:8]}…` 로드 실패 (권한 또는 ID 확인 필요): {str(e)[:120]}"
                )
            except Exception:
                pass

    if not records and source_errors:
        # 전부 실패한 경우만 raise
        raise RuntimeError(
            "모든 Notion 데이터 소스 로드 실패. 인테그레이션 권한을 확인하세요. "
            + "; ".join(f"{sid[:8]}: {err[:80]}" for sid, err in source_errors)
        )

    df = pd.DataFrame(records)
    if df.empty:
        return df
    # 날짜 컬럼 datetime 변환
    for c in ("계약일", "계약종료일"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["총매출"] = pd.to_numeric(df["총매출"], errors="coerce").fillna(0)
    return df


# 연도 라벨 (진단 표시용) — DATA_SOURCE_IDS 순서와 대응
_SOURCE_LABELS = {
    DATA_SOURCE_IDS[0]: "2026",
    DATA_SOURCE_IDS[1]: "2025",
    DATA_SOURCE_IDS[2]: "2024",
    DATA_SOURCE_IDS[3]: "2023",
}


def notion_source_status() -> list[dict]:
    """앱의 Notion 토큰(integration)이 각 연도 데이터 소스를 실제로 조회할 수 있는지
    즉석 점검. 캐시를 쓰지 않아 항상 실측값이며, 각 소스가 보이는 '최신 추가일시'까지
    돌려줘 '앱이 어디까지 보는지'를 눈으로 확인할 수 있게 한다.

    반환: [{"label","id","ok", (성공 시) "latest","latest_name", (실패 시) "error"}]
    """
    token = _token()
    if not token:
        return [{"label": "토큰", "id": "-", "ok": False,
                 "error": "NOTION_TOKEN이 설정되지 않았습니다 (secrets.toml 또는 환경변수)"}]

    notion = Client(auth=token)
    out = []
    for ds_id in DATA_SOURCE_IDS:
        row = {"label": _SOURCE_LABELS.get(ds_id, ds_id[:8]), "id": ds_id}
        try:
            resp = notion.data_sources.query(
                data_source_id=ds_id,
                page_size=1,
                sorts=[{"timestamp": "created_time", "direction": "descending"}],
            )
            results = resp.get("results", [])
            row["ok"] = True
            if results:
                row["latest"] = results[0].get("created_time", "")
                row["latest_name"] = _prop(results[0], "Name")
            else:
                row["latest"] = None
        except Exception as e:  # noqa: BLE001 — 진단이므로 원문 메시지 그대로 노출
            row["ok"] = False
            row["error"] = str(e)[:300]
        out.append(row)
    return out


def explode_services(df: pd.DataFrame) -> pd.DataFrame:
    """서비스명(multi_select) 폭발 → 행별 1서비스."""
    tmp = df.copy()
    tmp["서비스명"] = tmp["서비스명"].apply(lambda x: x if x else ["(없음)"])
    return tmp.explode("서비스명")
