"""원스글로벌 회계 인사이트 — Navigation hub.

st.navigation으로 사이드바 라벨을 커스텀.
- 홈화면 (home.py)
- 계약 관리 (pages/1_💼_계약_관리.py)
- 회계 관리 (pages/2_🚨_회계_관리.py)
"""
from __future__ import annotations

import streamlit as st

from auth import require_auth

st.set_page_config(
    page_title="원스글로벌 회계 인사이트",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)
require_auth()

pages = [
    st.Page("home.py", title="홈화면", icon="🏠", default=True),
    st.Page("pages/1_💼_계약_관리.py", title="계약 관리", icon="💼"),
    st.Page("pages/2_🚨_회계_관리.py", title="회계 관리", icon="🚨"),
]
nav = st.navigation(pages)
nav.run()
