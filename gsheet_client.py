"""Google Sheets 클라이언트 (계약 관리용).

로컬 실행: Guy의 service-account.json 파일 사용
Streamlit Cloud: secrets.toml의 [gcp_service_account] 섹션 사용
"""
from __future__ import annotations

import json
import os

import gspread
import streamlit as st
from google.oauth2 import service_account

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

LOCAL_KEY_FILE = "/Users/will/claude/projects/Data Analytics/service-account.json"


@st.cache_resource
def _gspread_client():
    """gspread 클라이언트 (캐시됨)."""
    # Streamlit secrets 우선
    has_secret = False
    try:
        has_secret = "gcp_service_account" in st.secrets
    except Exception as e:
        raise RuntimeError(f"st.secrets 접근 실패: {type(e).__name__}: {e}")
    if has_secret:
        try:
            info = dict(st.secrets["gcp_service_account"])
        except Exception as e:
            raise RuntimeError(f"secrets 딕셔너리 변환 실패: {type(e).__name__}: {e}")
        # private_key 줄바꿈 정규화 (Streamlit이 \\n으로 변환했을 수 있음)
        if "private_key" in info and "\\n" in info["private_key"]:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        try:
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return gspread.authorize(creds)

        except Exception as e:
            raise RuntimeError(
                f"service account 인증 실패: {type(e).__name__}: {e}. "
                f"private_key 형식이 올바른지 확인하세요 (BEGIN/END PRIVATE KEY 줄 포함)."
            )
    # 로컬 fallback
    if os.path.exists(LOCAL_KEY_FILE):
        creds = service_account.Credentials.from_service_account_file(LOCAL_KEY_FILE, scopes=SCOPES)
        return gspread.authorize(creds)
    raise RuntimeError(
        "service account 자격증명을 찾을 수 없습니다. "
        "Streamlit secrets의 [gcp_service_account] 블록 누락."
    )


def get_sheet_id() -> str:
    """계약 관리 Sheet ID."""
    try:
        sid = st.secrets.get("CONTRACTS_SHEET_ID", "")
        if sid:
            return sid
    except Exception:
        pass
    return os.environ.get("CONTRACTS_SHEET_ID", "")


def open_contracts_sheet():
    """계약 Sheet 열기."""
    sheet_id = get_sheet_id()
    if not sheet_id:
        raise RuntimeError("CONTRACTS_SHEET_ID가 secrets에 설정되지 않았습니다.")
    return _gspread_client().open_by_key(sheet_id)


def get_worksheet(name: str):
    """탭 이름으로 워크시트 가져오기."""
    return open_contracts_sheet().worksheet(name)
