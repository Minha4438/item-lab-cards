"""렌더된 카드뉴스를 @how.abouthis 에 캐러셀(기본) 또는 슬라이드 릴스로 게시.

  python3 post.py work/cards/<id>/spec.json --dry-run   # 업로드·컨테이너 생성까지만 (게시 안 함)
  python3 post.py work/cards/<id>/spec.json --yes       # 실제 게시
  python3 post.py work/cards/<id>/spec.json --reel --yes  # reel.mp4 (reel.py로 생성)를 릴스로 게시

캐러셀:

1) out/*.jpg 를 howabouthis/<id>/ 로 복사 → 커밋 → 현재 브랜치에 push
2) raw.githubusercontent.com (커밋 SHA 고정 주소) 에서 열리는지 확인
3) Instagram API: 이미지별 컨테이너 → 캐러셀 컨테이너(캡션) → media_publish
4) tools/howabouthis/history.json 에 기록 후 커밋·push
릴스: reel.mp4 를 같은 방식으로 howabouthis/<id>/ 에 올린 뒤 video_url 로 넘긴다
(인스타 로그인 토큰은 resumable 업로드를 지원하지 않음 — 2026-10 확인).
"""
import glob
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CARDS_DIR, HISTORY, REPO_DIR, git, http, ig_api, load_json, save_json  # noqa: E402


def push():
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    for i, wait in enumerate([0, 2, 4, 8, 16]):
        time.sleep(wait)
        r = __import__("subprocess").run(["git", "-C", REPO_DIR, "push", "-u", "origin", branch],
                                         capture_output=True, text=True)
        if r.returncode == 0:
            return branch
        print("push 재시도…", r.stderr.strip()[-200:])
    raise SystemExit("git push 실패")


def repo_slug():
    url = git("remote", "get-url", "origin")
    m = re.search(r"([^/:]+)/([^/]+?)(?:\.git)?$", url)
    return f"{m.group(1)}/{m.group(2)}"


def wait_status(cid, what, tries=40):
    for _ in range(tries):
        st = ig_api(cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise SystemExit(f"{what} 처리 실패: {st}")
        time.sleep(3)
    raise SystemExit(f"{what} 처리 시간 초과")


def main():
    args = sys.argv[1:]
    if not args or not ({"--dry-run", "--yes"} & set(args)):
        raise SystemExit(__doc__)
    dry = "--dry-run" in args
    fmt = "reel" if "--reel" in args else "carousel"
    spec_path = os.path.abspath(args[0])
    base = os.path.dirname(spec_path)
    spec = load_json(spec_path)
    cid_ = spec["id"]
    if not re.fullmatch(r"[0-9A-Za-z._-]+", cid_):
        raise SystemExit("spec.id 는 영문/숫자/-_. 만 (URL에 쓰임)")
    imgs = sorted(glob.glob(os.path.join(base, "out", "*.jpg")))
    if fmt == "carousel" and not 2 <= len(imgs) <= 10:
        raise SystemExit(f"이미지 {len(imgs)}장 — 캐러셀은 2~10장")
    mp4 = os.path.join(base, "reel.mp4")
    if fmt == "reel" and not os.path.exists(mp4):
        raise SystemExit("reel.mp4 없음 — reel.py 로 먼저 만들기")
    caption = spec["caption"]
    if len(caption) > 2200 or caption.count("#") > 30:
        raise SystemExit("캡션은 2,200자·해시태그 30개 이하")
    if not dry and any(h.get("id") == cid_ and h.get("platform", "instagram") == "instagram"
                       and h.get("format", "carousel") == fmt for h in load_json(HISTORY, [])):
        raise SystemExit(f"{cid_} ({fmt}) 는 이미 게시됨 (history.json)")

    quota = ig_api("me/content_publishing_limit", {"fields": "quota_usage,config"})["data"][0]
    print(f"오늘 게시 한도: {quota['quota_usage']}/{quota['config']['quota_total']}")
    uid = ig_api("me", {"fields": "user_id"})["user_id"]

    # 1) 공개 저장소에 올리기
    dst = os.path.join(CARDS_DIR, cid_)
    os.makedirs(dst, exist_ok=True)
    files = [mp4] if fmt == "reel" else imgs
    if fmt == "carousel":
        for f in glob.glob(os.path.join(dst, "*.jpg")):
            os.remove(f)
    for f in files:
        shutil.copy(f, dst)
    pub_spec = {k: v for k, v in spec.items() if k in ("id", "product", "keyword", "category", "caption")}
    save_json(os.path.join(dst, "spec.json"), pub_spec)
    git("add", dst)
    if git("diff", "--cached", "--name-only"):
        git("commit", "-m", f"Add how.abouthis cards {cid_}")
    branch = push()
    sha = git("rev-parse", "HEAD")
    urls = [f"https://raw.githubusercontent.com/{repo_slug()}/{sha}/howabouthis/{cid_}/{os.path.basename(f)}" for f in files]

    # 2) 공개 주소 확인
    for u in urls:
        for _ in range(30):
            st, _b = http(u)
            if st == 200:
                break
            time.sleep(4)
        else:
            raise SystemExit(f"공개 주소가 열리지 않음: {u} (저장소가 비공개인지 확인)")
    print(f"파일 {len(urls)}개 공개 확인 ({branch}@{sha[:7]})")
    if fmt == "reel":
        container = reel_container(uid, urls[0], caption)
        if dry:
            print(f"\n[드라이런] 릴스 컨테이너 {container} 준비 완료 — 게시하지 않음 (24시간 후 자동 만료)")
            return
        publish(uid, container, spec, fmt, len(imgs))
        return

    # 3) Instagram
    children = []
    for i, u in enumerate(urls, 1):
        c = ig_api(f"{uid}/media", {"image_url": u, "is_carousel_item": "true"}, post=True)["id"]
        wait_status(c, f"{i}번 이미지")
        children.append(c)
        print(f"  {i}/{len(urls)} 업로드 완료")
    carousel = ig_api(f"{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}, post=True)["id"]
    wait_status(carousel, "캐러셀")
    if dry:
        print(f"\n[드라이런] 캐러셀 컨테이너 {carousel} 준비 완료 — 게시하지 않음 (24시간 후 자동 만료)")
        return

    publish(uid, carousel, spec, fmt, len(urls))


def reel_container(uid, video_url, caption):
    """릴스 컨테이너 생성(첫 프레임 = 표지가 썸네일) → 인스타가 영상을 가져가 처리할 때까지 대기."""
    cid = ig_api(f"{uid}/media", {"media_type": "REELS", "video_url": video_url, "caption": caption,
                                  "share_to_feed": "true", "thumb_offset": "0"}, post=True)["id"]
    print("릴스 컨테이너 생성 — 인스타 영상 처리 대기…")
    wait_status(cid, "릴스", tries=100)
    return cid


def publish(uid, container, spec, fmt, slides):
    media_id = ig_api(f"{uid}/media_publish", {"creation_id": container}, post=True)["id"]
    link = ig_api(media_id, {"fields": "permalink"}).get("permalink")
    print(f"\n게시 완료 ✅ {link}")

    # 4) 기록
    hist = load_json(HISTORY, [])
    hist.append({"id": spec["id"], "product": spec.get("product"), "keyword": spec["keyword"], "format": fmt,
                 "media_id": media_id, "permalink": link, "posted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                 "slides": slides})
    save_json(HISTORY, hist)
    git("add", HISTORY)
    git("commit", "-m", f"Log how.abouthis {fmt} {spec['id']}")
    push()


if __name__ == "__main__":
    main()
