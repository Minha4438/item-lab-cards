---
name: make-cards
description: 고른 제품으로 이거 어때?(@how.abouthis) 시안 A(톡 버블) 스타일 카드뉴스(1080x1350 캐러셀)·슬라이드 릴스와 캡션을 만들고 미리보기를 보여준다. "카드뉴스 만들어줘", "N번으로 만들어", /make-cards 에 사용. 승인되면 post-cards 로 이어진다.
---

# 카드뉴스 만들기 (/make-cards)

인자: 제품명 또는 find-items 후보 번호, (선택) 사진/영상 URL·릴스 shortcode, (선택) 형식 `릴스` / `캐러셀`.

**형식 정하기** (spec.json의 `"format": "carousel" | "reel"`):
- 인자에 `릴스`/`캐러셀`이 있으면 그대로.
- 없으면 A/B 테스트 중이므로 `tools/howabouthis/history.json`의 마지막 게시 형식과 **반대**로 제안한다 (기록 없으면 릴스). 사용자가 바꾸면 따른다.
- 테스트 비교: 게시 48시간 후 비팔로워 도달·공유·저장·팔로우 (CLAUDE.md 참고).

## 0. 준비
`bash tools/howabouthis/setup.sh` (폰트·Pillow). 작업 폴더: `work/cards/<id>/` — `id` = `YYYY-MM-DD-<영문슬러그>` (예: `2026-10-05-dish-rack`).

## 1. 사진 확보 → `work/cards/<id>/img/`
우선순위:
1. 사용자가 준 사진/영상 (URL 또는 업로드 파일): `prep.py images <폴더> <url…>` / `prep.py video <폴더> <url>`
2. 내 계정 릴스 장면: `prep.py own-reel <폴더> --shortcode <코드>` (저작권 음원 릴스는 원본을 못 받음)
3. 쿠팡 상품 이미지 (`market.py coupang` 결과의 이미지 URL, 키 있을 때) — 단색 배경 제품컷이라 1~2장만
4. 제조사·브랜드 공식 이미지 — 출처 확인
- ❌ 레퍼런스 계정(un_ni_item, ssokssok.daily 등)·타인 SNS 사진은 쓰지 않는다.
- 사진이 부족하면(최소 4장) 사용자에게 요청하고 멈춘다.

`prep.py`가 만든 `sheet.jpg`를 Read로 보고 컷을 고른다: 표지 1 + 본문 3~6 + CTA 1 (총 5~8장 권장, 최대 10).
- 영상 프레임에 **자막·워터마크가 박혀 있으면** `prep.py crop`으로 피해서 자르거나, 말풍선 위치(`bubble: top|bottom`)로 가린다.
- 4:5 비율로 자동 크롭(cover)되므로 초점은 `{"src": "...", "pos": "50% 30%"}` 로 조정.

## 2. 카피·spec 작성 → `work/cards/<id>/spec.json`
형식은 `tools/howabouthis/examples/sujeo/spec.json` 그대로. 카피 규칙은 [copy-guide.md](copy-guide.md) 를 **반드시** 읽고 따른다.

## 3. 렌더 & 자체 검수
`python3 tools/howabouthis/cards.py work/cards/<id>/spec.json` → `out/NN.jpg`, `preview.jpg`
- `preview.jpg`와 표지(`out/01.jpg`)를 Read로 직접 확인:
  - 글자 잘림·과도한 축소(자동 축소 후 너무 작으면 문구를 줄인다)
  - 말풍선이 제품 핵심 부분을 가리면 `bubble: "top"` 으로
  - 사진이 너무 흐리거나 어두우면 교체
- 문제 있으면 고쳐서 다시 렌더.

## 3-2. 릴스 (format이 reel일 때)
`python3 tools/howabouthis/reel.py work/cards/<id>/spec.json` → `reel.mp4`(1080x1920, 표지 3초·본문 2.5초·크로스페이드), `reel_preview.jpg`
- `reel_preview.jpg`를 Read로 확인: 카드가 화면 위쪽에 있고 아래 440px는 비어 있어야 함(릴스 하단 UI 영역).
- 배경은 각 장의 원본 사진을 흐리게 깐 것 — spec의 이미지 순서(표지, 본문, CTA)가 out/NN.jpg와 같아야 한다.
- 음원은 저작권 없는 파일만 `--audio`로. 인스타 음악은 API로 못 붙임 → 필요하면 게시 후 앱에서 추가하도록 안내.

## 4. 사용자 검토
- SendUserFile로 `preview.jpg` (+ 표지 원본) 전송. 릴스면 `reel.mp4`와 `reel_preview.jpg`도.
- 캡션 전문을 채팅에 보여준다.
- "이대로 올릴까요? 고칠 곳 있으면 말씀해주세요"라고 묻고 **멈춘다**. 수정 요청은 반영해서 다시 미리보기.
- 승인("올려", "게시해" 등)이 오면 `post-cards` 스킬로 진행.
