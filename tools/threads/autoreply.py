"""아이템연구소 스레드 자동 답글 — 제품·링크를 묻는 댓글에만 "프로필 링크 확인" 답글을 한 번 단다.

  python tools/threads/autoreply.py          # 미리보기 (답글 안 닮)
  python tools/threads/autoreply.py --live   # 실제로 답글

- 환경 변수 THREADS_ACCESS_TOKEN (GitHub Actions에서는 저장소 Secret)
- "댓글 달면 링크 줄게" 같은 유도는 하지 않는다 (Meta 참여 낚시 정책). 스스로 물어본 댓글에만 답한다
- 이미 우리 계정이 답한 댓글은 건너뛴다 (기록 파일 없이 매번 API로 확인)
- 공개 저장소의 Actions 기록은 누구나 볼 수 있으므로 댓글 내용·아이디·토큰은 출력하지 않고 개수만 출력한다
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://graph.threads.net/v1.0"
DAYS = 14          # 최근 며칠 동안 올린 글의 댓글만 본다
MAX_REPLIES = 20   # 한 번 돌 때 최대 답글 수
NO_MAP = Path(__file__).with_name("no_map.json")  # 게시물 id → 세트 번호 (있으면 답글에 No. 표시)

ASK = re.compile(
    r"뭐\s*써|뭐\s*쓰|뭐에요|뭐예요|뭔가요|뭐야|무슨\s*(제품|세제|거)|어떤\s*(제품|거|걸)|제품|상품|이름|브랜드|"
    r"어디(서|꺼|거|껀|제)|링크|구매|사고\s*싶|살래|사볼|정보\s*좀|알려\s*줘|알려\s*주")

MESSAGES = [
    "프로필 링크에 정리해뒀어{no}. 거기서 확인해줘",
    "써본 거 프로필 링크에 모아뒀어{no}. 번호 보고 찾으면 돼",
    "프로필 링크(리틀리)에 있어{no}. 확인해줘",
]


def call(method, path, **params):
    params["access_token"] = os.environ["THREADS_ACCESS_TOKEN"]
    data = urllib.parse.urlencode(params)
    url = f"{API}/{path}"
    req = (urllib.request.Request(f"{url}?{data}") if method == "GET"
           else urllib.request.Request(url, data=data.encode(), method="POST"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # 주소에 토큰이 있어서 상태 코드와 오류 종류만
        try:
            err = json.loads(e.read().decode()).get("error", {})
        except Exception:
            err = {}
        raise SystemExit(f"API 오류 {e.code} ({method} {path.split('/')[-1]}): {err.get('message', '')}") from None


def wait_ready(cid):
    for _ in range(24):
        s = call("GET", cid, fields="status").get("status")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise SystemExit(f"답글 컨테이너 실패: {s}")
        time.sleep(5)
    raise SystemExit("답글 컨테이너가 2분 넘게 준비 안 됨")


def main():
    if not os.environ.get("THREADS_ACCESS_TOKEN"):
        print("THREADS_ACCESS_TOKEN이 없어서 건너뜀 (저장소 Settings → Secrets → Actions에 추가)")
        return
    live = "--live" in sys.argv
    me = call("GET", "me", fields="id,username")["username"]
    since = datetime.now(timezone.utc) - timedelta(days=DAYS)
    no_map = json.loads(NO_MAP.read_text(encoding="utf-8")) if NO_MAP.exists() else {}

    posts = call("GET", "me/threads", fields="id,timestamp", limit=50).get("data", [])
    posts = [p for p in posts if datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S%z") >= since]

    seen = asked = done = sent = 0
    for post in posts:
        replies = call("GET", f"{post['id']}/replies", fields="id,text,username,timestamp", limit=100).get("data", [])
        for r in replies:
            if r.get("username") == me:
                continue
            seen += 1
            if not ASK.search(r.get("text") or ""):
                continue
            asked += 1
            sub = call("GET", f"{r['id']}/replies", fields="username", limit=100).get("data", [])
            if any(x.get("username") == me for x in sub):
                done += 1
                continue
            if sent >= MAX_REPLIES:
                continue
            no = no_map.get(post["id"])
            msg = MESSAGES[int(r["id"]) % len(MESSAGES)].format(no=f" (No.{no})" if no else "")
            if live:
                cid = call("POST", "me/threads", media_type="TEXT", text=msg, reply_to_id=r["id"])["id"]
                wait_ready(cid)
                call("POST", "me/threads_publish", creation_id=cid)
                time.sleep(3)
            sent += 1
    mode = "답글 단 수" if live else "답글 달 예정 (미리보기)"
    print(f"최근 {DAYS}일 글 {len(posts)}개 · 남이 단 댓글 {seen}개 · 제품·링크 질문 {asked}개 · 이미 답함 {done}개 · {mode} {sent}개")


if __name__ == "__main__":
    main()
