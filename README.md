# 💰 원스글로벌 회계 인사이트 + 계약 관리

Notion 2026 영업현황 DB와 Google Sheets를 결합한 Streamlit 멀티페이지 대시보드.

- **회계 인사이트 (`app.py`)**: Notion 영업현황 DB 실시간 분석
- **계약 관리 (`pages/1_💼_계약_관리.py`)**: Google Sheets 기반 계약·결제 회차 추적

> 계약 관리 첫 사용 전 [SETUP_CONTRACTS.md](SETUP_CONTRACTS.md) 참고.

## 주요 지표
- 전체 파이프라인 / 확정 매출 / 잠재 매출 / **미수금**
- 미수금 상세 (세금계산서 발행 / 입금 미완료)
- 월별 세금계산서 발행 매출
- 영업 파이프라인 상태별 분포
- 서비스별 확정 매출 TOP15
- 신규 vs 갱신 vs 일회성 비중
- 정산유형별 분포
- 계약 → 발행 지연 분석
- 자동 인사이트 알림

## 로컬 실행

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# secrets.toml에 NOTION_TOKEN 입력
streamlit run app.py
```

## 배포 (Streamlit Cloud)

1. GitHub repo로 push (`.streamlit/secrets.toml`은 제외 — gitignore 반영됨)
2. https://share.streamlit.io 에서 새 앱 생성, 이 repo·`app.py` 지정
3. Streamlit Cloud의 Settings → Secrets 에 `NOTION_TOKEN` 입력
4. 발급 URL을 `Onesglobal Internal` 랜딩 페이지 `accounting` 키에 등록

## 앱 잠자기 방지

Streamlit Community Cloud는 일정 기간 접속이 없으면 앱을 잠재운다
(`Zzzz — This app has gone to sleep due to inactivity` 화면).

`.github/workflows/keep-awake.yml`이 6시간마다 실제 브라우저로 앱에 접속해
세션을 맺어 잠들지 않게 유지한다. 이미 잠들어 있으면 wake 버튼까지 눌러 깨운다.

- 수동 실행: GitHub → Actions → **Keep Streamlit app awake** → Run workflow
- 앱 URL 변경 시 workflow의 `APP_URL` 수정
- 실패하면 스크린샷이 artifact(`keep-awake-screenshot`)로 남는다

> repo에 60일 이상 커밋이 없으면 GitHub이 스케줄 워크플로를 자동 비활성화한다.
> 그 경우 Actions 탭에서 다시 활성화하면 된다.

## 데이터 출처

- Notion 영업현황 DB (data_source_id: `2ab3a733-4743-8132-91a6-000bdac816e9`)
- 캐싱: 10분 (`@st.cache_data(ttl=600)`)
