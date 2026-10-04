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


def _load_dotenv(path=os.path.join(REPO_DIR, ".env")):
    """저장소 루트 .env(gitignore)의 키를 환경 변수로. 이미 설정된 환경 변수가 우선, 빈 값은 무시."""
    try:
        f = open(path, encoding="utf-8-sig")
    except FileNotFoundError:
        return
    with f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().removeprefix("export ").strip(), v.strip().strip("\"'")
            if v:
                os.environ.setdefault(k, v)


_load_dotenv()

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


TYPES = {"GraphSidecar": "캐러셀", "GraphVideo": "릴스", "GraphImage": "사진",
         "CAROUSEL_ALBUM": "캐러셀", "VIDEO": "릴스", "IMAGE": "사진"}


def _from_web(u):
    posts = []
    for e in u["edge_owner_to_timeline_media"]["edges"]:
        n = e["node"]
        cap = n["edge_media_to_caption"]["edges"]
        posts.append({
            "shortcode": n["shortcode"], "url": f"https://www.instagram.com/p/{n['shortcode']}/",
            "type": TYPES.get(n["__typename"], n["__typename"]), "ts": n["taken_at_timestamp"],
            "caption": cap[0]["node"]["text"] if cap else "",
            "comments": n["edge_media_to_comment"]["count"], "likes": n["edge_liked_by"]["count"],
            "views": n.get("video_view_count"), "image": n["display_url"],
            "slides": len(n.get("edge_sidecar_to_children", {}).get("edges", [])) or 1,
            "pinned": bool(n.get("pinned_for_users")),
        })
    return {"followers": u["edge_followed_by"]["count"], "posts": posts}


def _from_business_discovery(handle, ig_id, token):
    import datetime as dt
    fields = (f"business_discovery.username({handle}){{followers_count,media.limit(24)"
              "{caption,like_count,comments_count,timestamp,media_type,media_url,thumbnail_url,permalink,children{id}}}")
    st, body = http(f"https://graph.facebook.com/v21.0/{ig_id}?" + urllib.parse.urlencode({"fields": fields, "access_token": token}))
    d = json.loads(body or b"{}")
    if st != 200:
        raise RuntimeError(f"business_discovery 실패 ({st}): {d.get('error', {}).get('message')}")
    bd = d["business_discovery"]
    posts = []
    for m in bd.get("media", {}).get("data", []):
        posts.append({
            "shortcode": m["permalink"].rstrip("/").split("/")[-1], "url": m["permalink"],
            "type": TYPES.get(m["media_type"], m["media_type"]),
            "ts": dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").timestamp(),
            "caption": m.get("caption", ""), "comments": m.get("comments_count", 0), "likes": m.get("like_count", 0),
            "views": None, "image": m.get("thumbnail_url") or m.get("media_url"),
            "slides": len(m.get("children", {}).get("data", [])) or 1, "pinned": False,
        })
    return {"followers": bd.get("followers_count"), "posts": posts}


def public_profile(handle, retries=6, wait=60, cache_hours=6):
    """다른 계정의 팔로워 수 + 최근 게시물(정규화). 순서: 캐시 → 공식 API(business_discovery) → 공개 웹 엔드포인트.

    공식 API는 Facebook 로그인 기반 토큰이 필요: 환경 변수 IG_FB_ACCESS_TOKEN(EAA…), IG_FB_BUSINESS_ID(178…).
    공개 웹 엔드포인트는 클라우드 IP에서 자주 429로 막힌다 — 기다렸다 재시도.
    """
    cache = os.path.join(WORK_DIR, "cache", f"{handle}.json")
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < cache_hours * 3600:
        return load_json(cache)
    tok, ig_id = os.environ.get("IG_FB_ACCESS_TOKEN"), os.environ.get("IG_FB_BUSINESS_ID")
    if tok and ig_id:
        prof = _from_business_discovery(handle, ig_id, tok)
        save_json(cache, prof)
        return prof
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={handle}"
    for i in range(retries):
        st, body = http(url, headers={"x-ig-app-id": IG_WEB_APP_ID})
        if st == 200:
            prof = _from_web(json.loads(body)["data"]["user"])
            save_json(cache, prof)
            return prof
        if st == 404:
            raise RuntimeError(f"@{handle} 계정을 찾을 수 없음")
        print(f"  @{handle}: {st} — {wait}s 후 재시도 ({i + 1}/{retries})", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"@{handle} 수집 실패 (인스타 요청 제한). 몇 분 뒤 다시 시도하세요.")


def git(*args, check=True):
    return subprocess.run(["git", "-C", REPO_DIR, *args], check=check, capture_output=True, text=True).stdout.strip()
