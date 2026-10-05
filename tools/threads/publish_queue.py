"""아이템연구소 스레드 예약 게시 — GitHub Actions가 돌린다 (Claude 사용량 없이 게시).

queue/ 폴더의 예약 파일(JSON) 중 시간이 된 게시물을 한 번에 1개씩 올린다.
  python tools/threads/publish_queue.py          # 미리보기 (올릴 게시물만 표시)
  python tools/threads/publish_queue.py --live   # 실제 게시 + 예약 파일에 결과 기록

예약 파일 (스레드 폴더의 threads_publish.py queue 명령이 만든다):
  {"key": "No4-A2", "run_at": "2026-10-05T23:00:00+09:00", "text": "...", "topic": "살림",
   "images": ["No4/A2/01.png", ...], "reply": null 또는 "2/2 본문", "no": "3", "status": "pending"}
status: pending → done (id·permalink 기록). B에서 1/2만 올라가고 2/2가 실패하면 reply_pending
- 토큰 계정이 @item.lab.kr이 아니면 아무것도 하지 않는다
- 같은 본문이 최근 글에 이미 있으면 올리지 않고 done(duplicate)으로 표시 (중복 게시 방지)
- 공개 저장소라 실행 기록에는 게시물 이름과 게시 주소만 남긴다
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://graph.threads.net/v1.0"
EXPECTED = "item.lab.kr"
HERE = Path(__file__).resolve().parent
QUEUE = HERE / "queue"
NO_MAP = HERE / "no_map.json"
RAW = "https://raw.githubusercontent.com/Minha4438/item-lab-cards/main"


def call(method, path, **params):
    params["access_token"] = os.environ["THREADS_ACCESS_TOKEN"]
    data = urllib.parse.urlencode(params)
    url = f"{API}/{path}"
    req = (urllib.request.Request(f"{url}?{data}") if method == "GET"
           else urllib.request.Request(url, data=data.encode(), method="POST"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # 주소에 토큰이 있어서 오류 내용만
        try:
            err = json.loads(e.read().decode()).get("error", {})
        except Exception:
            err = {}
        raise RuntimeError(f"API 오류 {e.code}: {err.get('error_user_msg') or err.get('message', '')}") from None


def wait_ready(cid):
    for _ in range(60):
        s = call("GET", cid, fields="status").get("status")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"컨테이너 실패: {s}")
        time.sleep(5)
    raise RuntimeError("컨테이너가 5분 넘게 준비 안 됨")


def publish(cid):
    mid = call("POST", "me/threads_publish", creation_id=cid)["id"]
    return mid, call("GET", mid, fields="permalink").get("permalink")


def post_main(job):
    extra = {"topic_tag": job["topic"]} if job.get("topic") else {}
    urls = [f"{RAW}/{p}" for p in job.get("images", [])]
    if not urls:
        cid = call("POST", "me/threads", media_type="TEXT", text=job["text"], **extra)["id"]
    elif len(urls) == 1:
        cid = call("POST", "me/threads", media_type="IMAGE", image_url=urls[0], text=job["text"], **extra)["id"]
    else:
        children = []
        for u in urls:
            c = call("POST", "me/threads", media_type="IMAGE", image_url=u, is_carousel_item="true")["id"]
            wait_ready(c)
            children.append(c)
        cid = call("POST", "me/threads", media_type="CAROUSEL", children=",".join(children), text=job["text"], **extra)["id"]
    wait_ready(cid)
    return publish(cid)


def post_reply(job, parent):
    cid = call("POST", "me/threads", media_type="TEXT", text=job["reply"], reply_to_id=parent)["id"]
    wait_ready(cid)
    return publish(cid)


KST = timezone(timedelta(hours=9))
MAX_TRIES = 3  # 같은 예약이 3번 실패하면 failed로 멈춤 (계속 재시도하지 않게)


def now_kst():
    return datetime.now(KST).isoformat(timespec="minutes")


def main():
    live = "--live" in sys.argv
    if not os.environ.get("THREADS_ACCESS_TOKEN"):
        print("토큰이 없어서 건너뜀 (Secrets에 ITEMLAB_THREADS_TOKEN)")
        return
    me = call("GET", "me", fields="username")["username"]
    if me != EXPECTED:
        print(f"토큰 계정이 @{me} — @{EXPECTED} 토큰이 아니라서 건너뜀")
        return

    now = datetime.now(timezone.utc)
    jobs = []
    for f in sorted(QUEUE.glob("*.json")):
        job = json.loads(f.read_text(encoding="utf-8"))
        if job.get("status") in ("pending", "reply_pending") and datetime.fromisoformat(job["run_at"]) <= now:
            jobs.append((datetime.fromisoformat(job["run_at"]), f, job))
    if not jobs:
        print("시간이 된 예약 게시물 없음")
        return
    jobs.sort(key=lambda x: x[0])
    _, f, job = jobs[0]  # 한 번에 1개씩 (밀린 게 여러 개여도 간격 유지)
    print(f"게시 대상: {job['key']} (예약 {job['run_at']}, 밀린 예약 {len(jobs)}개)")
    if not live:
        print("미리보기만 함")
        return

    def save():
        f.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        if job["status"] == "pending":
            recent = call("GET", "me/threads", fields="text,permalink", limit=50).get("data", [])
            same = [d for d in recent if (d.get("text") or "").strip() == job["text"].strip()]
            if same:
                job.update(status="done", note="같은 본문이 이미 있어 건너뜀", permalink=same[0].get("permalink"))
                save()
                print(f"{job['key']}: 같은 본문이 이미 올라가 있어서 건너뜀 {same[0].get('permalink')}")
                return
            mid, link = post_main(job)
            job.update(id=mid, permalink=link, published_at=now_kst(),
                       status="reply_pending" if job.get("reply") else "done")
            save()
            print(f"{job['key']} 게시 완료: {link}")
            if job.get("no"):  # 자동 답글이 이 글의 댓글에 "프로필 링크 n번"으로 안내하게
                m = json.loads(NO_MAP.read_text(encoding="utf-8")) if NO_MAP.exists() else {}
                m[mid] = job["no"]
                NO_MAP.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
            if job.get("reply"):
                time.sleep(10)
        if job["status"] == "reply_pending":
            rid, rlink = post_reply(job, job["id"])
            job.update(reply_id=rid, reply_permalink=rlink, status="done")
            save()
            print(f"{job['key']} 2/2 답글 게시 완료: {rlink}")
    except RuntimeError as e:
        job["last_error"] = f"{now_kst()} {e}"
        job["tries"] = job.get("tries", 0) + 1
        if job["tries"] >= MAX_TRIES:
            job["status"] = "failed"
        save()
        print(f"{job['key']} 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
