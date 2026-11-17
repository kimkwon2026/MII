# 명길의 보험 인사이트

보험설계사를 위한 보험·건강·의료 뉴스 큐레이션 웹앱 1차 버전입니다.

## 포함 기능
- 보험·금융·건강·질병·의료기관 관련 10개 카테고리
- Google News RSS 검색 피드 기반 정기 수집
- 키워드 검색, 최신순/오래된순 정렬
- 최근 7일·30일 필터
- 브라우저 로컬 스크랩
- 원문 링크 및 출처 표시
- 모바일/PC 반응형 화면

## GitHub에 배포하기

1. GitHub에서 새 Public repository를 만듭니다. 예: `myeonggil-insurance-insight`
2. 이 폴더의 파일 전체를 저장소 최상위(root)에 업로드합니다.
3. 저장소의 **Settings → Pages**로 이동합니다.
4. Build and deployment에서 **Source: GitHub Actions**를 선택합니다.
5. **Actions** 탭에서 `Update news feed`를 선택하고 **Run workflow**를 실행합니다.
6. 수집 작업이 완료되면 `data/news.json`이 갱신됩니다.

### Pages 배포 워크플로 추가
Settings → Pages에서 GitHub Actions를 선택하면 안내되는 정적 사이트 배포 워크플로를 사용할 수 있습니다. 가장 간단한 방법은 다음과 같습니다.

- 저장소의 Settings → Pages → Build and deployment → Deploy from a branch
- Branch: `main`, Folder: `/ (root)` 선택 후 Save

이 방식은 별도 빌드 없이 `index.html`을 게시합니다. 이후 주소는 보통
`https://<GitHub-사용자명>.github.io/<저장소명>/` 형태입니다.

## 자동 업데이트
`.github/workflows/update-news.yml`은 6시간마다 실행되도록 설정되어 있습니다. 시간은 UTC 기준이며, 수동 실행도 가능합니다.
GitHub Actions의 `workflow_dispatch`를 이용해 Actions 탭에서 즉시 수집할 수 있습니다.

## 수집 소스와 주의사항
`sources.json`의 검색어를 바꾸어 수집 범위를 조정할 수 있습니다. 현재는 Google News RSS 검색 결과를 활용하는 MVP입니다. 따라서 검색 결과에 공식기관 외 언론사 콘텐츠가 포함될 수 있으며, 공식기관의 모든 공지나 모든 병원 보도자료를 빠짐없이 수집한다고 보장하지 않습니다.

- 기사의 제목·요약·게시일·출처 표시는 RSS가 제공하는 범위에 따릅니다.
- 기사는 원문 링크로 연결하며 기사 전문을 복제하지 않습니다.
- 사이트별 RSS/API 제공 여부와 이용약관을 확인한 뒤 공식 피드를 추가하는 것을 권장합니다.
- 보험상품의 보장·보험료·인수기준 및 의료정보는 변경될 수 있으므로 실제 상담 전 반드시 최신 약관·공식 원문을 확인하세요.
- 스크랩은 현재 사용 중인 브라우저의 `localStorage`에 저장됩니다. 다른 기기와 동기화되지 않습니다.

## 다음 버전 후보
- 공식기관 RSS/API 직접 연결
- 보험사별 상품 변경 이력
- 기사별 AI 요약 및 설계사 관점의 핵심 포인트
- 사용자 계정 기반 스크랩 동기화
- 관심 키워드 알림 및 이메일 브리핑
