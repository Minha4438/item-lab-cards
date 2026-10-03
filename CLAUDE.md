# 작업 메모 (다음 세션이 꼭 읽을 것)

## 사용량 아끼기 — 같은 조회를 반복하지 않는다
- **vidIQ**: 크레딧 0. **2026-10-08에 재충전** — 그 전엔 vidIQ 도구를 호출하지 않는다.
  - 10/8 이후 할 일: 패션 레퍼런스 계정 찾기 (`vidiq_ig_accounts_from_outliers`, 10크레딧, 1회만). 지금 레퍼런스 목록은 살림·뷰티는 충분하고 패션이 부족함.
- **인스타 Graph API (business_discovery)**: 앱 단위 시간당 호출 한도가 있음. 2026-10-02에 계정 60여 개를 검증하다가 한도에 걸림.
  - `scout.py`는 계정당 1회 호출하고 `work/cache/`에 6시간 캐시한다. 같은 날 여러 번 돌리지 말고, 오늘자 `work/scout/<날짜>/candidates.json`이 있으면 그걸 쓴다.
  - 레퍼런스 후보 검증 결과는 `tools/howabouthis/refs_checked.json`. 여기 있는 계정은 다시 조회하지 않는다 (`pending`만 남음).
- **해시태그 검색 (ig_hashtag_search)**: 7일 동안 고유 해시태그 30개 한도. 2026-10-02에 10개 사용
  (꿀템추천·살림템·신박템·뷰티템·패션템·자취템·다이소꿀템·올리브영추천·쿠팡꿀템·꿀템). 10/9부터 다시 여유.
- **게시물 작성자 확인**: Graph API oEmbed는 권한이 없어 막힘. 공개 엔드포인트 `https://www.instagram.com/api/v1/oembed/?url=<게시물 URL>` (헤더 `x-ig-app-id`)로 `author_name`을 얻을 수 있음.
- 쿠팡 파트너스 키 없음 → `market.py coupang/best/goldbox`는 안 됨. 네이버 데이터랩(`market.py trend`)은 됨.

## 계정 방향
- @how.abouthis 니치: 살림·주방·인테리어 + **뷰티·패션** (2026-10-03부터 포함).
