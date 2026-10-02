"""이거 어때?(@how.abouthis) 카드뉴스 파이프라인 공용 유틸."""
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(TOOL_DIR))
WORK_DIR = os.path.join(REPO_DIR, "work")            # gitignore — 세션 임시 작업물
CARDS_DIR = os.path.join(REPO_DIR, "howabouthis")    # 공개 이미지 (Instagram이 여기서 가져감)
HISTORY = os.path.join(TOOL_DIR, "history.json")     # 게시 이력

IG_GRAPH = "https://graph.instagram.com/v21.0"
IG_WEB_APP_ID = "936619743392459"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128 Safari/537.36")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def http(url, data=None, headers=None, method=None, timeout=30):
    """(status, body_bytes). data가 dict면 form-encode."""
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def ig_token():
    tok = os.environ.get("INSTAGRAM_ACCESS_TOKEN_HOWABOUTHIS")
    if not tok:
        raise SystemExit("환경 변수 INSTAGRAM_ACCESS_TOKEN_HOWABOUTHIS 가 없습니다.")
    return tok


def ig_api(path, params=None, post=False):
    params = dict(params or {}, access_token=ig_token())
    url = f"{IG_GRAPH}/{path.lstrip('/')}"
    if post:
        st, body = http(url, data=params, method="POST")
    else:
        st, body = http(url + "?" + urllib.parse.urlencode(params))
    out = json.loads(body or b"{}")
    if st >= 400 or "error" in out:
        raise RuntimeError(f"IG API {path} 실패 ({st}): {out.get('error', out)}")
    return out


def public_profile(handle, retries=8, wait=45):
    """공개 프로필 + 최근 12개 게시물. 인스타가 잠깐 막으면(401/429) 기다렸다 재시도."""
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={handle}"
    for i in range(retries):
        st, body = http(url, headers={"x-ig-app-id": IG_WEB_APP_ID})
        if st == 200:
            return json.loads(body)["data"]["user"]
        if st == 404:
            raise RuntimeError(f"@{handle} 계정을 찾을 수 없음")
        print(f"  @{handle}: {st} — {wait}s 후 재시도 ({i + 1}/{retries})", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"@{handle} 수집 실패 (인스타 요청 제한). 몇 분 뒤 다시 시도하세요.")


def git(*args, check=True):
    return subprocess.run(["git", "-C", REPO_DIR, *args], check=check, capture_output=True, text=True).stdout.strip()
