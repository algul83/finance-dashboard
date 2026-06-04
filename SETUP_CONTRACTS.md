# 계약 관리 셋업 가이드

`💼 계약 관리` 페이지를 사용하기 위한 1회 셋업 (Lina님 작업).

## 1. Google Sheet 만들기 (1분)

1. https://sheets.google.com 접속 → **빈 스프레드시트 만들기**
2. 좌측 상단 파일명을 **`OnesGlobal Contracts`** 로 변경
3. 하단의 `Sheet1` 탭 우클릭 → **이름 바꾸기** → **`Contracts`**
4. 하단 **+** 버튼으로 새 시트 추가 → 이름 **`Payments`**

탭 두 개(`Contracts`, `Payments`) 이름이 정확해야 합니다. 헤더는 비워두세요 — 첫 동기화 시 자동으로 작성됩니다.

## 2. Service Account에게 Editor 권한 공유

1. 우측 상단 **공유** 버튼 클릭
2. 다음 이메일 추가 (역할 **편집자**, 알림 보내기 ❌):
   ```
   guy-dashboard-bot@guy-dashboard-bot.iam.gserviceaccount.com
   ```
3. **보내기**

## 3. Sheet ID 복사

브라우저 주소창의 URL에서 가운데 부분이 Sheet ID:

```
https://docs.google.com/spreadsheets/d/[이_부분이_Sheet_ID]/edit
```

예시 ID: `1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789`

## 4. Streamlit Cloud Secrets에 추가

1. https://share.streamlit.io 접속
2. `onesglobal-accounting` 앱 옆 ⋮ → **Settings → Secrets**
3. 기존 `NOTION_TOKEN` 아래에 다음 추가:

```toml
NOTION_TOKEN = "ntn_..."  # 기존 그대로

CONTRACTS_SHEET_ID = "여기에_위에서_복사한_Sheet_ID"

[gcp_service_account]
type = "service_account"
project_id = "guy-dashboard-bot"
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----
... (여러 줄)
-----END PRIVATE KEY-----
"""
client_email = "guy-dashboard-bot@guy-dashboard-bot.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

**`[gcp_service_account]` 블록 안의 실제 값들**은 제(William)가 별도로 전달해드릴 거예요 (Slack DM 등 안전한 채널로).

4. **Save** → 앱 자동 재시작

## 5. 첫 동기화

1. https://onesglobal-accounting.streamlit.app 접속
2. 좌측 사이드바에서 **💼 계약 관리** 페이지 클릭
3. 사이드바의 **🔄 Notion에서 신규 성사 건 가져오기** 클릭
4. 노션의 `성공·입금완료·정산완료` 27건이 Sheets에 자동 추가됨

이후 노션에서 새로 `성공` 상태가 되는 건은 같은 버튼으로 추가 가져올 수 있어요.
