"""스레드 공개 글·계정 탐색 결과를 요약해 로그에 출력 (threads-research.yml). 공개 저장소라 로그도 공개 → 글 전문은 안 찍고 앞부분 40자·반응 수·주소만.
환경: THREADS_ACCESS_TOKEN (Secret ITEMLAB_THREADS_TOKEN), QUERIES(쉼표로 구분), USERNAMES(쉼표, 선택), SEARCH_TYPE(TOP|RECENT)
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.threads.net/v1.0"
TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
FIELDS = "id,text,permalink,timestamp,username,like_count,reply_count,repost_count,quote_count,is_reply"


def get(path, **p):
    p["access_token"] = TOKEN
    try:
        with urllib.request.urlopen(f"{API}/{path}?{urllib.parse.urlencode(p)}", timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def short(t, n=40):
    return (t or "").replace("\n", " ")[:n]


def err(j):
    e = j.get("error", {})
    return f"code {e.get('code')} {e.get('message', '')}"[:160]


def main():
    stype = os.environ.get("SEARCH_TYPE", "TOP") or "TOP"
    for q in [x.strip() for x in os.environ.get("QUERIES", "").split(",") if x.strip()]:
        st, j = get("keyword_search", q=q, search_type=stype, fields=FIELDS)
        if st != 200:
            st, j = get("keyword_search", q=q, search_type=stype, fields="id,text,permalink,username")  # 필드 미지원 대비
        rows = j.get("data", []) if st == 200 else []
        print(f"\n## 검색 '{q}' ({stype}) — {len(rows)}건" + ("" if st == 200 else f" 실패 {err(j)}"))
        for r in sorted(rows, key=lambda x: -(x.get("like_count") or 0))[:15]:
            print(f"- @{r.get('username')} | 좋아요 {r.get('like_count')} 답글 {r.get('reply_count')} 리포스트 {r.get('repost_count')} | {short(r.get('text'))} | {r.get('permalink')}")
    for u in [x.strip().lstrip("@") for x in os.environ.get("USERNAMES", "").split(",") if x.strip()]:
        st, j = get("profile_lookup", username=u, fields="username,name,biography,is_verified,follower_count,likes_count,replies_count,reposts_count,views_count")
        if st != 200:
            st, j = get("profile_lookup", username=u, fields="username,name,biography")
        if st == 200:
            print(f"\n## 계정 @{u}: 팔로워 {j.get('follower_count')} | {short(j.get('biography'), 60)} | {j}"[:400])
        else:
            print(f"\n## 계정 @{u}: 실패 {err(j)}")
        st, j = get("profile_posts", username=u, fields=FIELDS, limit=25)
        rows = j.get("data", []) if st == 200 else []
        if st == 200:
            print(f"   최근 글 {len(rows)}건 — 좋아요 상위:")
            for r in sorted(rows, key=lambda x: -(x.get("like_count") or 0))[:5]:
                print(f"   - 좋아요 {r.get('like_count')} 답글 {r.get('reply_count')} | {short(r.get('text'))} | {r.get('permalink')}")
        else:
            print(f"   profile_posts 실패 {err(j)}")


if __name__ == "__main__":
    main()
