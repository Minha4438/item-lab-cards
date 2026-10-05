"""이거 어때?(@how.abouthis) 인스타 예약 게시 — 예약은 로컬(Claude)에서, 게시는 GitHub Actions가 한다.

  python tools/howabouthis/ig_queue.py add work/cards/<id>/spec.json --at "2026-10-06 20:00" [--reel] [--dry]
      승인된 카드를 howabouthis/<id>/ 에 올리고 queue/<id>.json 예약을 만들어 커밋·push (--dry: 확인만)
  python tools/howabouthis/ig_queue.py run           # 미리보기 (시간이 된 예약만 표시)
  python tools/howabouthis/ig_queue.py run --live    # 실제 게시 (howabouthis-ig-publish.yml)
  python tools/howabouthis/ig_queue.py list          # 예약 목록

예약 파일 tools/howabouthis/queue/<id>.json:
  {"id", "format": "carousel"|"reel", "run_at": "2026-10-06T20:00+09:00", "files": ["howabouthis/<id>/01.jpg", ...],
   "caption", "product", "keyword", "status": "pending"|"done"|"failed", "tries"}
- 토큰 계정이 @how.abouthis가 아니면 아무것도 하지 않는다
- 같은 캡션이 최근 게시물에 이미 있거나 history.json에 같은 id·형식이 있으면 올리지 않고 done(duplicate)
- 한 번 실행에 1개만 (밀린 예약이 여러 개여도 간격 유지), 3번 실패하면 failed로 멈춤
- 공개 저장소라 실행 기록에는 예약 이름과 게시 주소만 남긴다 (토큰·주소 쿼리는 출력하지 않음)
"""
import glob
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CARDS_DIR, HISTORY, REPO_DIR, TOOL_DIR, git, http, ig_api, load_json, save_json  # noqa: E402
from post import push, reel_container, repo_slug, wait_status  # noqa: E402

EXPECTED = "how.abouthis"
QUEUE = os.path.join(TOOL_DIR, "queue")
KST = timezone(timedelta(hours=9))
MAX_TRIES = 3


def rel(path):
    return os.path.relpath(path, REPO_DIR).replace(os.sep, "/")


def parse_at(s):
    dt = datetime.fromisoformat(s.strip().replace(" ", "T"))
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def add(args):
    spec_path = os.path.abspath(args[0])
    base = os.path.dirname(spec_path)
    spec = load_json(spec_path)
    cid = spec["id"]
    fmt = "reel" if "--reel" in args else spec.get("format", "carousel")
    if "--at" not in args:
        raise SystemExit('--at "YYYY-MM-DD HH:MM" (KST) 이 필요합니다')
    run_at = parse_at(args[args.index("--at") + 1])
    if run_at <= datetime.now(KST):
        raise SystemExit(f"예약 시각 {run_at:%m/%d %H:%M}이 이미 지났습니다")
    if any(h.get("id") == cid and h.get("platform", "instagram") == "instagram"
           and h.get("format", "carousel") == fmt for h in load_json(HISTORY, [])):
        raise SystemExit(f"{cid} ({fmt}) 는 이미 게시됨 (history.json)")
    qpath = os.path.join(QUEUE, f"{cid}.json")
    old = load_json(qpath)
    if old and old.get("status") == "pending":
        print(f"기존 예약({old['run_at']})을 새 시각으로 바꿉니다")

    if fmt == "reel":
        src = [os.path.join(base, "reel.mp4")]
    else:
        src = sorted(glob.glob(os.path.join(base, "out", "*.jpg")))
        if not 2 <= len(src) <= 10:
            raise SystemExit(f"이미지 {len(src)}장 — 캐러셀은 2~10장")
    if not all(os.path.exists(f) for f in src):
        raise SystemExit(f"파일 없음: {src}")
    caption = spec["caption"]
    if len(caption) > 2200 or caption.count("#") > 30:
        raise SystemExit("캡션은 2,200자·해시태그 30개 이하")

    dst = os.path.join(CARDS_DIR, cid)
    files = [rel(os.path.join(dst, os.path.basename(f))) for f in src]
    job = {"id": cid, "format": fmt, "run_at": run_at.isoformat(timespec="minutes"), "files": files,
           "caption": caption, "product": spec.get("product"), "keyword": spec["keyword"],
           "status": "pending", "tries": 0}
    print(f"예약: {cid} ({fmt}, {len(files)}개 파일) → {run_at:%Y-%m-%d %H:%M} KST")
    if "--dry" in args:
        print("--dry: 파일·커밋은 하지 않음")
        return

    os.makedirs(dst, exist_ok=True)
    if fmt == "carousel":
        for f in glob.glob(os.path.join(dst, "*.jpg")):
            os.remove(f)
    for f in src:
        shutil.copy(f, dst)
    save_json(os.path.join(dst, "spec.json"),
              {k: v for k, v in spec.items() if k in ("id", "product", "keyword", "category", "caption")})
    os.makedirs(QUEUE, exist_ok=True)
    save_json(qpath, job)
    git("add", dst, qpath)
    if git("diff", "--cached", "--name-only"):
        git("commit", "-m", f"Schedule how.abouthis {fmt} {cid} for {run_at:%m/%d %H:%M} KST")
    push()
    print("예약 완료 — GitHub Actions(howabouthis-ig-publish)가 시간이 되면 게시합니다")


def due_jobs():
    now = datetime.now(timezone.utc)
    jobs = []
    for f in sorted(glob.glob(os.path.join(QUEUE, "*.json"))):
        job = load_json(f)
        if job.get("status") == "pending" and parse_at(job["run_at"]) <= now:
            jobs.append((parse_at(job["run_at"]), f, job))
    return sorted(jobs, key=lambda x: x[0])


def publish_job(uid, job):
    sha = os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD")
    urls = [f"https://raw.githubusercontent.com/{repo_slug()}/{sha}/{p}" for p in job["files"]]
    for u in urls:
        st, _ = http(u)
        if st != 200:
            raise RuntimeError(f"공개 주소가 열리지 않음: {u.rsplit('/', 1)[-1]}")
    if job["format"] == "reel":
        container = reel_container(uid, urls[0], job["caption"])
    else:
        children = []
        for i, u in enumerate(urls, 1):
            c = ig_api(f"{uid}/media", {"image_url": u, "is_carousel_item": "true"}, post=True)["id"]
            wait_status(c, f"{i}번 이미지")
            children.append(c)
        container = ig_api(f"{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(children),
                                            "caption": job["caption"]}, post=True)["id"]
        wait_status(container, "캐러셀")
    media_id = ig_api(f"{uid}/media_publish", {"creation_id": container}, post=True)["id"]
    return media_id, ig_api(media_id, {"fields": "permalink"}).get("permalink")


def run(args):
    live = "--live" in args
    if not os.environ.get("INSTAGRAM_ACCESS_TOKEN_HOWABOUTHIS"):
        print("토큰이 없어서 건너뜀 (Secrets에 HOWABOUTHIS_IG_TOKEN)")
        return
    me = ig_api("me", {"fields": "user_id,username"})
    if me.get("username") != EXPECTED:
        print(f"토큰 계정이 @{me.get('username')} — @{EXPECTED} 토큰이 아니라서 건너뜀")
        return
    jobs = due_jobs()
    if not jobs:
        print("시간이 된 예약 게시물 없음")
        return
    _, qpath, job = jobs[0]
    print(f"게시 대상: {job['id']} ({job['format']}, 예약 {job['run_at']}, 밀린 예약 {len(jobs)}개)")
    if not live:
        print("미리보기만 함")
        return

    hist = load_json(HISTORY, [])
    recent = ig_api("me/media", {"fields": "caption,permalink", "limit": 25}).get("data", [])
    same = [m for m in recent if (m.get("caption") or "").strip() == job["caption"].strip()]
    posted = [h for h in hist if h.get("id") == job["id"] and h.get("platform", "instagram") == "instagram"
              and h.get("format", "carousel") == job["format"]]
    if same or posted:
        link = same[0].get("permalink") if same else posted[0].get("permalink")
        job.update(status="done", note="이미 게시돼 있어 건너뜀", permalink=link)
        save_json(qpath, job)
        print(f"{job['id']}: 이미 게시돼 있어서 건너뜀 {link}")
        return

    try:
        media_id, link = publish_job(me["user_id"], job)
    except (RuntimeError, SystemExit) as e:
        job["tries"] = job.get("tries", 0) + 1
        if job["tries"] >= MAX_TRIES:
            job["status"] = "failed"
        job["last_error"] = str(e)[:200]
        save_json(qpath, job)
        raise SystemExit(f"{job['id']} 게시 실패 ({job['tries']}/{MAX_TRIES}): {str(e)[:200]}")

    posted_at = datetime.now(KST).isoformat(timespec="seconds")
    job.update(status="done", media_id=media_id, permalink=link, published_at=posted_at)
    save_json(qpath, job)
    hist.append({"id": job["id"], "product": job.get("product"), "keyword": job["keyword"], "format": job["format"],
                 "media_id": media_id, "permalink": link, "posted_at": posted_at,
                 "slides": len(job["files"]) if job["format"] == "carousel" else 1, "via": "actions"})
    save_json(HISTORY, hist)
    print(f"{job['id']} 게시 완료: {link}")


def list_jobs():
    for f in sorted(glob.glob(os.path.join(QUEUE, "*.json"))):
        j = load_json(f)
        print(f"{j['status']:<8} {j['run_at']}  {j['id']} ({j['format']}) {j.get('permalink', '')}")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else ""
    if cmd == "add" and len(a) >= 2:
        add(a[1:])
    elif cmd == "run":
        run(a[1:])
    elif cmd == "list":
        list_jobs()
    else:
        raise SystemExit(__doc__)
