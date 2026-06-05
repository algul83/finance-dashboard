"""공통 로그인 게이트 — main + 모든 sub-page 상단에서 require_auth() 호출.

비밀번호는 Streamlit Cloud Secrets의 `app_password` 키로 설정.
secrets 미설정 시 게이트는 우회 (로컬 개발용).

URL token 우회 — anchor 링크 클릭으로 인한 session reset을 방지하기 위해
`?auth=<token>` query param으로 자동 인증.
"""
from __future__ import annotations

import hashlib
import os

import streamlit as st

PRIMARY = "#5B43C9"


def _stored_password() -> str:
    try:
        return st.secrets.get("app_password", "")
    except Exception:
        return os.environ.get("APP_PASSWORD", "")


def _token() -> str:
    pw = _stored_password()
    if not pw:
        return ""
    return hashlib.sha256(pw.encode()).hexdigest()[:16]


def auth_query_suffix() -> str:
    """페이지 간 anchor 링크에 붙일 ?auth=<token> 쿼리 (인증 시에만)."""
    token = _token()
    return f"&auth={token}" if token else ""


def require_auth():
    """모든 페이지 상단에서 호출. 인증 안 됐으면 로그인 폼 표시 + st.stop()."""
    if st.session_state.get("authenticated"):
        return

    pw = _stored_password()
    if not pw:
        # 비밀번호 설정 안 됨 → 게이트 우회 (로컬 개발용)
        return

    # URL token으로 자동 인증
    token = _token()
    if token and st.query_params.get("auth") == token:
        st.session_state["authenticated"] = True
        return

    # 로그인 폼
    st.markdown(
        f'<div style="max-width:420px;margin:80px auto;padding:36px 28px;'
        f'background:white;border-radius:14px;box-shadow:0 4px 18px rgba(91,67,201,0.12);'
        f'text-align:center;">'
        f'<div style="font-size:1.6rem;font-weight:800;color:{PRIMARY};margin-bottom:6px;">'
        f'💰 회계 인사이트</div>'
        f'<div style="color:#8B8A95;font-size:0.9rem;margin-bottom:24px;">'
        f'사내 직원 전용 — 비밀번호를 입력하세요</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    c = st.columns([1, 2, 1])
    with c[1]:
        entered = st.text_input(
            "비밀번호",
            type="password",
            label_visibility="collapsed",
            placeholder="비밀번호 입력",
            key="login_pwd",
        )
        if st.button("로그인", use_container_width=True, type="primary"):
            if entered == pw:
                st.session_state["authenticated"] = True
                st.query_params["auth"] = token
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    st.stop()
