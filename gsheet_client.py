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
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return gspread.authorize(creds)
    except Exception:
        pass
    # 로컬 fallback
    if os.path.exists(LOCAL_KEY_FILE):
        creds = service_account.Credentials.from_service_account_file(LOCAL_KEY_FILE, scopes=SCOPES)
        return gspread.authorize(creds)
    raise RuntimeError(
        "service account 자격증명을 찾을 수 없습니다. "
        "Streamlit secrets의 [gcp_service_account] 또는 로컬 service-account.json 필요."
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
