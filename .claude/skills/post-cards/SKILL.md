---
name: post-cards
description: make-cards로 만들고 사용자가 승인한 카드뉴스를 @how.abouthis 인스타그램에 캐러셀로 게시한다. "올려", "게시해", /post-cards 에 사용. 사용자가 이 대화에서 해당 카드의 게시를 명시적으로 승인한 경우에만 실행.
---

# 게시하기 (/post-cards)

인자: 카드 id (생략 시 이 대화에서 마지막으로 만든 카드).

## 규칙
- **이 대화에서 사용자가 그 카드(미리보기)를 보고 게시를 승인했을 때만** 실제 게시한다. 승인이 없거나 애매하면 미리보기와 캡션을 다시 보여주고 확인을 받는다.
- 이전 대화·다른 카드에 대한 승인은 해당되지 않는다.

## 실행
1. `work/cards/<id>/out/*.jpg`와 `spec.json`이 있는지 확인. 없으면 make-cards부터.
2. `python3 tools/howabouthis/post.py work/cards/<id>/spec.json --yes`
   - 이미지를 `howabouthis/<id>/`로 커밋·푸시 → 공개 주소 확인 → 인스타 캐러셀 게시 → `history.json` 기록·푸시.
   - 테스트만 할 때는 `--dry-run` (게시 직전까지, 컨테이너는 24시간 후 자동 만료).
3. 결과 보고: 게시물 링크(permalink) + 사용자가 할 일:
   - 자동 DM 도구에 키워드 `'<keyword>'` 등록 (아직 자동화 안 됨)
   - 프로필 링크 페이지에 제품 링크 추가 (쿠팡 키가 있으면 `market.py deeplink <쿠팡URL>`로 파트너스 링크 생성)

## 오류
- `code 190` / 토큰 만료: 인스타 장기 토큰은 60일마다 갱신 필요. Meta 개발자 콘솔에서 새 토큰을 발급해 환경 변수 `INSTAGRAM_ACCESS_TOKEN_HOWABOUTHIS`를 교체하도록 안내 (환경 설정은 read_documentation 의 environment.secrets 참고).
- `공개 주소가 열리지 않음`: 저장소가 비공개로 바뀌었는지 확인.
- 게시 한도(24시간 100건) 초과 시 다음 날로.
- 실패해도 이미 게시된 건 아닌지 `ig me/media` 로 최근 게시물을 확인한 뒤 재시도 (중복 게시 방지).
