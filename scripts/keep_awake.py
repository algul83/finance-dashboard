"""Streamlit Community Cloud 앱 keep-alive 핑.

Cloud 앱은 일정 기간 접속이 없으면 잠자기 모드("Zzzz")로 내려간다.
단순 HTTP GET은 활동으로 집계되지 않을 수 있어, 실제 브라우저로 접속해
websocket 세션을 맺고(필요하면 wake 버튼까지 눌러) 깨워둔다.

환경변수:
  APP_URL       대상 앱 URL (기본: onesglobal-accounting)
  WAKE_TIMEOUT  wake 후 앱 로딩 대기 초 (기본 300)
  HOLD_SECONDS  세션 유지 초 (기본 25)
  CHROMIUM_PATH 크로미움 실행 파일 경로 (기본: playwright 번들)
"""
from __future__ import annotations

import os
import sys
import time

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "https://onesglobal-accounting.streamlit.app")
WAKE_TIMEOUT = int(os.environ.get("WAKE_TIMEOUT", "300"))
HOLD_SECONDS = int(os.environ.get("HOLD_SECONDS", "25"))
SHOT = os.environ.get("SCREENSHOT_PATH", "keep_awake.png")
CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH") or None


def log(msg: str) -> None:
    print(f"[keep-awake] {msg}", flush=True)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM_PATH)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            log(f"open {URL}")
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)

            wake = page.get_by_role("button", name="get this app back up", exact=False)
            try:
                wake.wait_for(state="visible", timeout=15_000)
                log("잠자기 상태 감지 → wake 버튼 클릭")
                wake.click()
            except PWTimeout:
                log("잠자기 아님 — 이미 깨어 있음")

            # Streamlit 앱 루트가 뜨면 부팅 완료.
            page.wait_for_selector('[data-testid="stApp"]', timeout=WAKE_TIMEOUT * 1_000)
            log("앱 로딩 완료")

            # websocket 세션을 잠시 유지해야 '활동'으로 집계된다.
            time.sleep(HOLD_SECONDS)
            page.screenshot(path=SHOT, full_page=False)
            log("정상 종료")
            return 0
        except Exception as exc:  # noqa: BLE001 — 실패 원인을 로그로 남기고 non-zero
            log(f"실패: {type(exc).__name__}: {exc}")
            try:
                page.screenshot(path=SHOT, full_page=False)
            except Exception:
                pass
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
