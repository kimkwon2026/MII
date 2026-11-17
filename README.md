# 명길의 보험 인사이트 v2

모바일 우선 반응형 뉴스 큐레이션 웹앱입니다.

## 추가된 기능
- 스마트폰 하단 고정 메뉴: 홈/보험/건강/병원/스크랩
- 오늘의 핵심 뉴스 TOP 10 (최신성 및 키워드 기반 간이 점수)
- 기존 10개 카테고리, 검색, 기간 필터, 스크랩
- 기존 GitHub Actions RSS 자동 수집 유지

## 배포
기존 GitHub 저장소에서 `index.html`, `styles.css`, `app.js`를 각각 교체하고 Commit changes 하세요. 기존 `.github/workflows/update-news.yml`, `scripts/fetch_news.py`, `sources.json`, `data/news.json`은 유지합니다.

## 갱신 주기
워크플로 cron `17 */6 * * *`이면 UTC 기준 00:17, 06:17, 12:17, 18:17에 실행되도록 예약됩니다. 한국시간으로는 09:17, 15:17, 21:17, 다음날 03:17입니다. GitHub Actions는 예약 실행을 지연할 수 있고 비활성 저장소 등 조건에 따라 실행되지 않을 수 있습니다. Actions 탭에서 성공 여부를 확인하세요.

## 한계
TOP 10은 AI 편집이 아니라 최신성·제목 키워드에 기반한 간이 자동 선정입니다. 기사 요약은 RSS description이며, AI 요약·상담 포인트 생성은 API 연동이 필요한 후속 기능입니다. 스크랩은 브라우저별 로컬 저장입니다.
