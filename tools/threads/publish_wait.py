"""예약 게시 대기 실행기 (2026-10-12) — 정해진 시각까지 기다렸다가 그 시각에 올린다 (Claude 사용량 없음).

GitHub 예약(cron)이 5시간 안팎으로만 돌아서 예약이 밀리는 문제를 피한다.
  - 예약 파일이 push 되거나 수동 실행하면 시작해서, 가장 이른 예약 시각까지 sleep 하고 publish_queue.py --live 로 게시한다
  - 한 번에 최대 5시간 30분 실행 (GitHub 작업 제한 6시간). 다음 예약이 그보다 멀면 스스로 새 실행을 시작해 이어 간다
  - cron 실행은 예비 감시용: 같은 스크립트를 돌린다
  - 게시 사이 최소 15분 간격, 실패하면 5분 뒤 재시도 (publish_queue.py가 3번 실패하면 failed로 멈춤)
  python tools/threads/publish_wait.py --plan    # 다음 예약과 대기 시간만 표시
공개 저장소라 로그에는 게시물 이름과 시각만 남긴다.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
QUEUE = HERE / "queue"
KST = timezone(timedelta(hours=9))
RUN_LIMIT = 330 * 60   # 한 번에 최대 5시간 30분
SAFETY = 120           # 마감 직전 여유
MIN_GAP = 15 * 60      # 게시 사이 최소 간격
RETRY_WAIT = 300
MAX_LOOPS = 60
RELAY_MAX = 24 * 3600  # 다음 예약이 이보다 멀면 이어가지 않음 (push·cron이 다시 시작함)


def say(msg):
    print(msg, flush=True)


def pending():
    out = []
    for f in sorted(QUEUE.glob("*.json")):
        try:
            job = json.loads(f.read_text(encoding="utf-8"))
            if job.get("status") in ("pending", "reply_pending"):
                out.append((datetime.fromisoformat(job["run_at"]), job["key"]))
        except Exception:
            continue
    return sorted(out)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def sync():
    git("config", "user.name", "threads-publish-bot")
    git("config", "user.email", "actions@users.noreply.github.com")
    r = git("pull", "--rebase", "origin", "main")
    if r.returncode != 0:
        git("rebase", "--abort")
        say("git pull 실패 — 현재 파일로 계속")


def commit_push():
    git("add", "tools/threads/queue", "tools/threads/no_map.json")
    if git("diff", "--cached", "--quiet").returncode != 0:
        git("commit", "-m", "threads-publish: 게시 결과 기록")
        for _ in range(3):
            git("pull", "--rebase", "origin", "main")
            if git("push").returncode == 0:
                return
            time.sleep(5)
        say("결과 push 실패 — 마지막 단계에서 다시 시도")


def dispatch():
    r = subprocess.run(["gh", "workflow", "run", "threads-publish.yml", "--ref", "main"], cwd=ROOT,
                       capture_output=True, text=True)
    say("다음 실행 예약 " + ("완료" if r.returncode == 0 else f"실패({r.stderr.strip()[:80]})"))


def main():
    plan = "--plan" in sys.argv
    start = time.time()
    deadline = start + RUN_LIMIT
    last_post = 0.0
    for _ in range(MAX_LOOPS):
        sync()
        jobs = pending()
        if not jobs:
            say("남은 예약 없음")
            return
        run_at, key = jobs[0]
        wait = max((run_at - datetime.now(timezone.utc)).total_seconds(), last_post + MIN_GAP - time.time(), 0)
        say(f"다음: {key} (예약 {run_at.astimezone(KST):%m/%d %H:%M} KST, 대기 {int(wait // 60)}분, 남은 예약 {len(jobs)}개)")
        if plan:
            return
        if time.time() + wait > deadline - SAFETY:
            if wait > RELAY_MAX:
                say("다음 예약이 24시간 넘게 남아 이어가지 않음 (push·예약 실행이 다시 시작)")
                return
            nap = max(deadline - SAFETY - time.time(), 0)
            say(f"이번 실행 시간이 모자라 {int(nap // 60)}분 쉬었다가 다음 실행에 넘김")
            time.sleep(nap)
            sync()
            if pending():
                dispatch()
            return
        time.sleep(wait + 3)  # 시계 오차로 1~2초 일찍 깨어나도 시간이 된 뒤에 확인
        r = subprocess.run([sys.executable, "tools/threads/publish_queue.py", "--live"], cwd=ROOT, env=os.environ)
        commit_push()
        if r.returncode != 0:
            say("게시 실패 — 5분 뒤 다시 시도")
            time.sleep(RETRY_WAIT)
        elif len(pending()) < len(jobs) or any(k != key for _, k in pending()[:1]):
            last_post = time.time()  # 게시되어 이번 예약이 끝남
        else:
            time.sleep(20)  # 게시된 게 없으면(시각 직전) 잠깐 뒤 다시 확인
    sync()
    if pending():
        dispatch()


if __name__ == "__main__":
    main()
