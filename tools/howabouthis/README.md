# 이거 어때?(@how.abouthis) 카드뉴스 파이프라인

Claude Code 세션에서 명령어로 실행:

| 명령 | 하는 일 |
|---|---|
| `/제품검색 [조건]` (`/find-items`) | 레퍼런스 계정·웹·시즌·(쿠팡/네이버)로 후보 5개 추천 → 사용자가 선택 |
| `/만들기 <제품> [릴스\|캐러셀]` (`/make-cards`) | 사진 준비 → 카피·spec 작성 → 시안 A 렌더 (+ 슬라이드 릴스) → 미리보기 → 사용자 검토 |
| `/올리기 [id] [릴스\|캐러셀]` (`/post-cards`) | 승인된 카드 → 공개 저장소 푸시 → 인스타 캐러셀·릴스 게시 → 이력 기록 |

| 파일 | 역할 |
|---|---|
| `scout.py` | 레퍼런스 계정(refs.json) 최근 게시물을 평소 댓글 대비 배수로 순위화 |
| `market.py` | 쿠팡 파트너스(검색·골드박스·베스트·딥링크)·네이버 데이터랩 — 키 있을 때만 |
| `prep.py` | 사진 준비 (내 릴스/영상 장면 추출, URL 다운로드, 자르기, 한눈에 보기) |
| `cards.py` + `render.js` | spec.json → 1080x1350 JPG (시안 A, 넘치는 글자 자동 축소) |
| `reel.py` | 렌더된 카드 → 슬라이드 릴스 `reel.mp4` (1080x1920) |
| `post.py` | 게시 (`--reel`: 릴스, `--dry-run`: 게시 직전까지만) |
| `history.json` | 게시 이력 (중복 방지) |
| `examples/sujeo/` | 예시 spec + 사진 |

환경 변수: `INSTAGRAM_ACCESS_TOKEN_HOWABOUTHIS`(필수), `COUPANG_ACCESS_KEY`/`COUPANG_SECRET_KEY`, `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`(+ API HUB 키면 `NAVER_API_HUB=1`), `IG_FB_ACCESS_TOKEN`/`IG_FB_BUSINESS_ID`(선택 — 레퍼런스 계정 공식 API 수집).
작업 파일은 `work/`(git 제외), 게시용 공개 이미지는 `howabouthis/<id>/`.

## 윈도우(로컬)에서 실행

`setup.sh`는 리눅스용이라 윈도우에서는 아래를 한 번 실행한다 (PowerShell).

```powershell
winget install Git.Git Python.Python.3.12 OpenJS.NodeJS.LTS Gyan.FFmpeg
# 터미널을 새로 연 뒤, 저장소 폴더에서
pip install pillow
npm install playwright
npx playwright install chromium
```

- 폰트: [Pretendard](https://github.com/orioncactus/pretendard/releases) zip을 받아 `public/static/*.otf`를 모두 선택 → 우클릭 → **모든 사용자용으로 설치**.
- API 키: 저장소 루트의 `.env.example`을 복사해 이름을 `.env`로 바꾸고, 메모장으로 열어 `=` 뒤에 값을 붙여 넣으면 끝.
  모든 스크립트가 `common.py`에서 자동으로 읽는다. `.env`는 gitignore라 커밋되지 않는다.
  (환경 변수로 이미 설정된 값이 있으면 그쪽이 우선.)
- `work/`(스캔 캐시·작업 이미지)는 git에 없으므로 로컬에서 새로 만들어진다.
