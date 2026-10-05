"""스레드 장기 토큰 갱신 → GitHub Secret 교체. threads-token-refresh.yml이 매월 1·15일에 돌린다.

장기 토큰은 60일 유효. 발급 후 24시간이 지나야 갱신 가능하고, 갱신하면 다시 60일.
- Secret 값을 환경 변수로 받아 갱신하고, 새 값은 gh secret set 으로 바로 저장 (화면에 출력하지 않음)
- 하나가 실패해도 나머지는 계속하고, 마지막에 실패로 끝나서 GitHub이 알림 메일을 보내게 한다
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SECRETS = ("ITEMLAB_THREADS_TOKEN", "HOWABOUTHIS_THREADS_TOKEN")
URL = "https://graph.threads.net/refresh_access_token"


def refresh(token):
    q = urllib.parse.urlencode({"grant_type": "th_refresh_token", "access_token": token})
    try:
        with urllib.request.urlopen(f"{URL}?{q}", timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # 주소에 토큰이 있어서 오류 내용만
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"갱신 실패 {e.code}: {msg}") from None


def main():
    if not os.environ.get("GH_TOKEN"):
        sys.exit("Secret SECRETS_PAT 이 없어서 새 토큰을 저장할 수 없음 — 갱신하지 않음")
    failed = 0
    for name in SECRETS:
        token = os.environ.get(name)
        if not token:
            print(f"{name}: Secret 없음 — 건너뜀")
            continue
        try:
            out = refresh(token)
            new = out["access_token"]
            print(f"::add-mask::{new}")
            subprocess.run(["gh", "secret", "set", name, "--repo", os.environ["GITHUB_REPOSITORY"]],
                           input=new, text=True, check=True, capture_output=True)
            print(f"{name}: 갱신 완료 — {out.get('expires_in', 0) // 86400}일 유효")
        except (RuntimeError, subprocess.CalledProcessError, KeyError) as e:
            failed += 1
            detail = e.stderr.strip()[-200:] if isinstance(e, subprocess.CalledProcessError) else e
            print(f"{name}: {detail}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
