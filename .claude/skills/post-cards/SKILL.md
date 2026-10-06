---
name: post-cards
description: make-cards로 만들고 사용자가 승인한 카드뉴스를 @how.abouthis 인스타그램에 캐러셀 또는 슬라이드 릴스로 게시한다. "올려", "게시해", /post-cards 에 사용. 사용자가 이 대화에서 해당 카드의 게시를 명시적으로 승인한 경우에만 실행.
---

# 게시하기 (/post-cards)

인자: 카드 id (생략 시 이 대화에서 마지막으로 만든 카드), (선택) `릴스`/`캐러셀` — 없으면 spec.json의 `format` (없으면 캐러셀).

## 규칙
- **이 대화에서 사용자가 그 카드(미리보기)를 보고 게시를 승인했을 때만** 실제 게시한다. 승인이 없거나 애매하면 미리보기와 캡션을 다시 보여주고 확인을 받는다.
- 이전 대화·다른 카드에 대한 승인은 해당되지 않는다.

## 실행
1. `work/cards/<id>/out/*.jpg`와 `spec.json`이 있는지 확인. 없으면 make-cards부터.
2. **기본은 예약 게시 (2026-10-05 사용자 결정 — GitHub Actions가 올린다, 시각은 카드마다 사용자가 정함)**:
   - 승인과 함께 게시 시각을 받는다. 시각을 말하지 않았으면 묻는다 (KST, "10/7 20:00"처럼).
   - `python tools/howabouthis/ig_queue.py add work/cards/<id>/spec.json --at "YYYY-MM-DD HH:MM" [--reel]`
     → 이미지를 `howabouthis/<id>/`에, 예약을 `tools/howabouthis/queue/<id>.json`에 커밋·push.
     `.github/workflows/howabouthis-ig-publish.yml`이 30분마다(:02/:32) 확인해 시간이 된 1개를 게시하고 history.json을 커밋한다 (몇~수십 분 늦을 수 있음).
   - 예약 확인: `ig_queue.py list`. 시각 변경은 같은 명령을 새 `--at`으로 다시.
   - 토큰: Secret `HOWABOUTHIS_IG_TOKEN`, `threads-token-refresh.yml`이 매월 1·15일 같이 갱신.
   - 결과 보고: 예약 시각 + 리틀리 문구(아래 4) — 게시물 링크는 Actions가 올린 뒤 `ig_queue.py list` 또는 history.json에서.
3. 사용자가 "지금 바로 올려"라고 하면 즉시 게시 — 캐러셀: `python3 tools/howabouthis/post.py work/cards/<id>/spec.json --yes`
   - 이미지를 `howabouthis/<id>/`로 커밋·푸시 → 공개 주소 확인 → 인스타 캐러셀 게시 → `history.json` 기록·푸시.
   릴스: `python3 tools/howabouthis/post.py work/cards/<id>/spec.json --reel --yes` (`reel.mp4` 필요 — 없으면 `reel.py`부터)
   - `reel.mp4`를 `howabouthis/<id>/`로 커밋·푸시 → video_url로 릴스 컨테이너 → 처리 대기(최대 5분) → 게시 → 기록(`format: reel`).
   - 테스트만 할 때는 `--dry-run` (게시 직전까지, 컨테이너는 24시간 후 자동 만료).
4. 스레드 (사용자가 스레드 게시도 승인했을 때만):
   - 본문은 인스타 캡션을 그대로 쓰지 않고 스레드 말투로 새로 쓴다: 친구한테 말하듯 반말, 직접 써본 듯한 한두 문장,
     짧은 줄바꿈, 500자 이하, 해시태그 1개. 끝은 댓글 유도. `work/cards/<id>/threads.txt`에 저장하고 사용자에게 보여준 뒤 게시.
   - 프로필 링크의 제품 번호(`--no`)를 사용자에게 확인한다. 자동 답글 "댓글 감사합니다! 프로필 링크에서 N번 제품 확인해주세요~!"에 들어감.
   - `python3 tools/howabouthis/threads.py post <id> --text-file work/cards/<id>/threads.txt --no <N> --yes`
     (`howabouthis/<id>/`의 reel.mp4 또는 jpg를 그대로 씀. 숏폼 렌더 영상은 `--video <mp4 경로>`)
   - 자동 답글은 GitHub Actions(`howabouthis-threads-autoreply.yml`)가 30분마다 `threads.py reply`로 처리 — 모든 댓글에 한 번씩. 수동 확인은 `--dry-run`.
   - 토큰은 `threads-token-refresh.yml`이 매월 1·15일 갱신 (Secret `HOWABOUTHIS_THREADS_TOKEN`, `SECRETS_PAT` 필요).
5. 결과 보고: 게시물 링크(permalink) + 사용자가 할 일:
   - 자동 DM 도구(리틀리)에 키워드 `'<keyword>'` 등록 — **[littly-templates.md](littly-templates.md)의 공개 답글 4개·DM 메시지·팔로우 안내를
     이 게시물에 맞게 채워서 코드 블록으로 같이 준다** (2026-10-05 사용자 요청, 매 게시마다)
   - 프로필 링크 페이지에 제품 링크 추가 (쿠팡 키가 있으면 `market.py deeplink <쿠팡URL>`로 파트너스 링크 생성)

## 오류
- `code 190` / 토큰 만료: 인스타 장기 토큰은 60일마다 갱신 필요. Meta 개발자 콘솔에서 새 토큰을 발급해 환경 변수 `INSTAGRAM_ACCESS_TOKEN_HOWABOUTHIS`를 교체하도록 안내 (환경 설정은 read_documentation 의 environment.secrets 참고).
- `공개 주소가 열리지 않음`: 저장소가 비공개로 바뀌었는지 확인.
- 게시 한도(24시간 100건) 초과 시 다음 날로.
- 실패해도 이미 게시된 건 아닌지 `ig me/media` 로 최근 게시물을 확인한 뒤 재시도 (중복 게시 방지).
