"""스레드 인증 코드 → 장기 토큰(60일) 발급 → GitHub Secret ITEMLAB_THREADS_TOKEN 교체. threads-token-issue.yml이 손으로 돌린다.
(터미널 없이 폰에서 토큰을 받기 위한 것. 코드·시크릿·토큰은 화면에 출력하지 않고, 결과 상태만 출력)

필요 Secret: THREADS_APP_ID, THREADS_APP_SECRET, THREADS_AUTH_CODE(1회용 코드), SECRETS_PAT(Secrets 읽기·쓰기)
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.threads.net"
REDIRECT = os.environ.get("THREADS_REDIRECT_URI", "https://example.com/")


def call(method, url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def err(j):
    e = j.get("error", {}) if isinstance(j, dict) else {}
    return f"code {e.get('code')} {e.get('message', '')}".strip()


def clean_code(raw):
    raw = raw.strip()
    m = re.search(r"[?&]code=([^&#\s]+)", raw)  # 주소 전체를 붙여 넣은 경우
    if m:
        raw = m.group(1)
    return raw.split("#")[0].strip()


def need(name):
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"Secret {name} 이 비어 있음 — 코드를 쓰기 전에 멈춤")
    return v


def main():
    app_id, secret, pat = need("THREADS_APP_ID"), need("THREADS_APP_SECRET"), need("GH_TOKEN")
    code = clean_code(need("THREADS_AUTH_CODE"))
    print(f"::add-mask::{code}")

    st, j = call("POST", f"{API}/oauth/access_token", {
        "client_id": app_id, "client_secret": secret, "grant_type": "authorization_code",
        "redirect_uri": REDIRECT, "code": code})
    if st != 200 or "access_token" not in j:
        sys.exit(f"1단계(코드→단기 토큰) 실패 {st}: {err(j)} — 코드는 1회용·1시간. 새 코드로 다시")
    short = j["access_token"]
    print(f"::add-mask::{short}")
    print("1단계 단기 토큰 받음")

    q = urllib.parse.urlencode({"grant_type": "th_exchange_token", "client_secret": secret, "access_token": short})
    st, j = call("GET", f"{API}/access_token?{q}")
    if st != 200 or "access_token" not in j:
        sys.exit(f"2단계(단기→장기) 실패 {st}: {err(j)}")
    token = j["access_token"]
    print(f"::add-mask::{token}")
    print(f"2단계 장기 토큰 받음 — {j.get('expires_in', 0) // 86400}일 유효")

    st, me = call("GET", f"{API}/v1.0/me?fields=id,username&access_token={token}")
    if st != 200:
        sys.exit(f"새 토큰 확인 실패 {st}: {err(me)} — Secret은 바꾸지 않음")
    print(f"계정 확인: @{me.get('username')}")

    q = urllib.parse.urlencode({"q": "야식", "search_type": "TOP", "fields": "id", "access_token": token})
    st, j = call("GET", f"{API}/v1.0/keyword_search?{q}")
    print("keyword_search:", f"OK — {len(j.get('data', []))}건" if st == 200 else f"막힘 ({err(j)})")
    q = urllib.parse.urlencode({"username": "threads", "access_token": token})
    st, j = call("GET", f"{API}/v1.0/profile_lookup?{q}")
    print("profile_lookup:", "OK" if st == 200 else f"막힘 ({err(j)})")

    subprocess.run(["gh", "secret", "set", "ITEMLAB_THREADS_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
                   input=token, text=True, check=True, capture_output=True)
    print("ITEMLAB_THREADS_TOKEN 교체 완료. THREADS_AUTH_CODE 는 이미 썼으니 지워도 됨")


if __name__ == "__main__":
    main()
