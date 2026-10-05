"""@how.abouthis 스레드 게시 · 댓글 자동 답글 · 토큰 갱신.

  python threads.py post <id> --text-file t.txt --no 3 --dry-run   # 컨테이너 준비까지만 (게시 안 함)
  python threads.py post <id> --text-file t.txt --no 3 --yes       # 실제 게시
  python threads.py post <id> --video final.mp4 --text-file t.txt --no 3 --yes   # 다른 곳에서 렌더한 영상
  python threads.py reply [--days 14] [--dry-run]                  # 새 댓글에 자동 답글
  python threads.py refresh                                        # 토큰 갱신 (.env 교체)

게시: howabouthis/<id>/ 에 이미 올라간 reel.mp4(영상) 또는 *.jpg(캐러셀)를 그대로 쓴다.
  --video 를 주면 그 mp4를 howabouthis/<id>/video.mp4 로 커밋·푸시해서 쓴다.
  본문(--text-file)은 스레드 말투로 따로 쓴다 (500자, 해시태그 1개). --no 는 프로필 링크의 제품 번호.
답글: history.json 의 스레드 게시물에 달린 남의 댓글(최상위) 중 아직 답하지 않은 것에 REPLY_TEMPLATE 로 답한다.
  이미 답했는지는 스레드 대화에서 내 답글을 보고 판단 (상태 파일 없음).
  GitHub Actions(howabouthis-threads-autoreply.yml)가 30분마다 돌린다 — 공개 저장소라 로그에는 개수만 남긴다.
토큰: 로컬(.env 있음)에서는 만료 15일 전이면 자동 갱신. Actions Secret은 threads-token-refresh.yml이 갱신.
"""
import glob
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CARDS_DIR, HISTORY, REPO_DIR, git, http, load_json, save_json  # noqa: E402
from post import push, repo_slug  # noqa: E402

TH_GRAPH = "https://graph.threads.net/v1.0"
REPLY_TEMPLATE = "댓글 감사합니다! 프로필 링크에서 {no}번 제품 확인해주세요~!"
REFRESH_BEFORE_DAYS = 15
EXPECTED = "how.abouthis"  # 이 계정 토큰일 때만 답글 (같은 저장소에 @item.lab.kr도 있음)
MAX_REPLIES = 20  # 한 번 돌 때 최대 답글 수
ENV_PATH = os.path.join(REPO_DIR, ".env")


def th_token():
    tok = os.environ.get("THREADS_ACCESS_TOKEN")
    if not tok:
        raise SystemExit("환경 변수 THREADS_ACCESS_TOKEN 이 없습니다 (.env).")
    return tok


def th_api(path, params=None, post=False):
    params = dict(params or {}, access_token=th_token())
    url = path if path.startswith("http") else f"{TH_GRAPH}/{path.lstrip('/')}"
    if post:
        st, body = http(url, data=params, method="POST")
    else:
        st, body = http(url + "?" + urllib.parse.urlencode(params))
    out = json.loads(body or b"{}")
    if st >= 400 or "error" in out:
        raise RuntimeError(f"Threads API {path} 실패 ({st}): {out.get('error', out)}")
    return out


def wait_status(cid, what, tries=40):
    for _ in range(tries):
        st = th_api(cid, {"fields": "status,error_message"})
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"{what} 처리 실패: {st}")
        time.sleep(3)
    raise SystemExit(f"{what} 처리 시간 초과")


def publish_container(cid):
    media_id = th_api("me/threads_publish", {"creation_id": cid}, post=True)["id"]
    return media_id, th_api(media_id, {"fields": "permalink"}).get("permalink")


# ---------- 토큰 ----------

def token_expires_at():
    tok = th_token()
    return th_api("debug_token", {"input_token": tok})["data"].get("expires_at") or 0


def refresh_token():
    out = th_api("https://graph.threads.net/refresh_access_token", {"grant_type": "th_refresh_token"})
    new = out["access_token"]
    with open(ENV_PATH, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    lines = [l for l in lines if not l.strip().startswith("THREADS_ACCESS_TOKEN=")] + [f"THREADS_ACCESS_TOKEN={new}"]
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.environ["THREADS_ACCESS_TOKEN"] = new
    print(f"스레드 토큰 갱신 완료 — {out.get('expires_in', 0) // 86400}일 유효 (.env 교체)")


def maybe_refresh():
    if not os.path.exists(ENV_PATH):  # Actions에서는 Secret을 threads-token-refresh.yml이 갱신
        return
    left = (token_expires_at() - time.time()) / 86400
    if left < REFRESH_BEFORE_DAYS:
        refresh_token()


# ---------- 게시 ----------

def cmd_post(args):
    cid_ = args[0] if args and not args[0].startswith("--") else None
    if not cid_ or not re.fullmatch(r"[0-9A-Za-z._-]+", cid_):
        raise SystemExit(__doc__)
    if not ({"--dry-run", "--yes"} & set(args)):
        raise SystemExit(__doc__)
    dry = "--dry-run" in args
    opt = lambda k: args[args.index(k) + 1] if k in args else None  # noqa: E731
    text_file, no, video = opt("--text-file"), opt("--no"), opt("--video")
    if not text_file or not no or not no.isdigit():
        raise SystemExit("--text-file 과 --no <프로필 링크 제품 번호> 가 필요합니다")
    with open(text_file, encoding="utf-8-sig") as f:
        text = f.read().strip()
    if len(text) > 500:
        raise SystemExit(f"본문 {len(text)}자 — 스레드는 500자 이하")
    if text.count("#") > 1:
        raise SystemExit("스레드는 해시태그(토픽) 1개만 적용됨 — 1개로 줄이기")
    hist = load_json(HISTORY, [])
    if not dry and any(h.get("id") == cid_ and h.get("platform") == "threads" for h in hist):
        raise SystemExit(f"{cid_} 는 이미 스레드에 게시됨 (history.json)")

    if not dry:
        maybe_refresh()
    q = th_api("me/threads_publishing_limit", {"fields": "quota_usage,config"})["data"][0]
    print(f"오늘 스레드 게시 한도: {q['quota_usage']}/{q['config']['quota_total']}")

    dst = os.path.join(CARDS_DIR, cid_)
    if video:
        os.makedirs(dst, exist_ok=True)
        shutil.copy(video, os.path.join(dst, "video.mp4"))
        git("add", dst)
        if git("diff", "--cached", "--name-only"):
            git("commit", "-m", f"Add how.abouthis threads video {cid_}")
        push()
    mp4 = next((p for p in (os.path.join(dst, n) for n in ("video.mp4", "reel.mp4")) if os.path.exists(p)), None)
    files = [mp4] if mp4 else sorted(glob.glob(os.path.join(dst, "*.jpg")))
    if not files:
        raise SystemExit(f"howabouthis/{cid_}/ 에 영상·이미지 없음 — post.py 로 먼저 올리거나 --video 지정")
    rel = os.path.relpath(dst, REPO_DIR).replace(os.sep, "/")
    sha = git("log", "-1", "--format=%H", "--", rel)
    if not sha or git("branch", "-r", "--contains", sha, check=False) == "":
        raise SystemExit(f"{rel} 가 아직 푸시되지 않음 — git push 먼저")
    urls = [f"https://raw.githubusercontent.com/{repo_slug()}/{sha}/{rel}/{os.path.basename(f)}" for f in files]
    for u in urls:
        if http(u)[0] != 200:
            raise SystemExit(f"공개 주소가 열리지 않음: {u}")

    if mp4:
        fmt = "video"
        cid = th_api("me/threads", {"media_type": "VIDEO", "video_url": urls[0], "text": text}, post=True)["id"]
        print("영상 컨테이너 생성 — 스레드 영상 처리 대기…")
        wait_status(cid, "영상", tries=100)
    elif len(urls) == 1:
        fmt = "image"
        cid = th_api("me/threads", {"media_type": "IMAGE", "image_url": urls[0], "text": text}, post=True)["id"]
        wait_status(cid, "이미지")
    else:
        fmt = "carousel"
        children = []
        for i, u in enumerate(urls[:20], 1):
            c = th_api("me/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true"}, post=True)["id"]
            wait_status(c, f"{i}번 이미지")
            children.append(c)
        cid = th_api("me/threads", {"media_type": "CAROUSEL", "children": ",".join(children), "text": text}, post=True)["id"]
        wait_status(cid, "캐러셀")
    if dry:
        print(f"\n[드라이런] 스레드 {fmt} 컨테이너 {cid} 준비 완료 — 게시하지 않음")
        print(f"자동 답글: {REPLY_TEMPLATE.format(no=no)}")
        return

    media_id, link = publish_container(cid)
    print(f"\n스레드 게시 완료 ✅ {link}")
    hist.append({"id": cid_, "platform": "threads", "format": fmt, "media_id": media_id, "permalink": link,
                 "posted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "link_no": int(no)})
    save_json(HISTORY, hist)
    git("add", HISTORY)
    git("commit", "-m", f"Log how.abouthis threads {cid_}")
    push()


# ---------- 자동 답글 ----------

def conversation(media_id):
    items, page = [], th_api(f"{media_id}/conversation",
                             {"fields": "id,username,is_reply_owned_by_me,replied_to,hide_status", "limit": 100})
    while True:
        items += page.get("data", [])
        nxt = page.get("paging", {}).get("next")
        if not nxt:
            return items
        st, body = http(nxt)
        page = json.loads(body)


def cmd_reply(args):
    dry = "--dry-run" in args
    days = int(args[args.index("--days") + 1]) if "--days" in args else 14
    if not os.environ.get("THREADS_ACCESS_TOKEN"):
        print("토큰이 없어서 건너뜀 (Secrets에 HOWABOUTHIS_THREADS_TOKEN)")
        return
    me = th_api("me", {"fields": "username"})["username"]
    if me != EXPECTED:
        print(f"토큰 계정이 @{EXPECTED} 가 아니라서 건너뜀")
        return
    if not dry:
        maybe_refresh()
    cutoff = time.time() - days * 86400
    posts = [h for h in load_json(HISTORY, []) if h.get("platform") == "threads"
             and time.mktime(time.strptime(h["posted_at"][:19], "%Y-%m-%dT%H:%M:%S")) >= cutoff]
    if not posts:
        print(f"최근 {days}일 스레드 게시물 없음")
        return
    left = None
    if not dry:
        q = th_api("me/threads_publishing_limit", {"fields": "reply_quota_usage,reply_config"})["data"][0]
        left = q["reply_config"]["quota_total"] - q["reply_quota_usage"]
    sent = 0
    for p in posts:
        conv = conversation(p["media_id"])
        answered = {(r.get("replied_to") or {}).get("id") for r in conv if r.get("is_reply_owned_by_me")}
        todo = [r for r in conv if not r.get("is_reply_owned_by_me")
                and (r.get("replied_to") or {}).get("id") == p["media_id"]
                and r.get("hide_status") not in ("HIDDEN", "COVERED")
                and r["id"] not in answered]
        print(f"{p['id']}: 새 댓글 {len(todo)}개 (프로필 링크 {p['link_no']}번)")
        text = REPLY_TEMPLATE.format(no=p["link_no"])
        for r in todo:
            if dry:
                print(f"  [드라이런] → {text}")
                continue
            if sent >= MAX_REPLIES or (left is not None and left <= 0):
                print(f"이번 실행 한도 도달 — 답글 {sent}개 보냄, 나머지는 다음 실행 때")
                return
            if sent:
                time.sleep(random.uniform(8, 15))  # 같은 문구를 몰아서 달면 스팸으로 걸릴 수 있음
            c = th_api("me/threads", {"media_type": "TEXT", "text": text, "reply_to_id": r["id"]}, post=True)["id"]
            wait_status(c, "답글")
            publish_container(c)
            sent += 1
            left = left - 1 if left is not None else None
    print(f"답글 {sent}개 보냄")


def main():
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else (None, [])
    if cmd == "post":
        cmd_post(args)
    elif cmd == "reply":
        cmd_reply(args)
    elif cmd == "refresh":
        refresh_token()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
