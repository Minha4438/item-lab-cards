"""쿠팡 파트너스·네이버 데이터랩 연동 (키가 있을 때만 동작).

  python3 market.py coupang "물빠짐 수저통"          # 상품 검색: 가격·로켓·평점·파트너스 링크·이미지
  python3 market.py goldbox                          # 쿠팡 골드박스(오늘의 특가)
  python3 market.py best 1015                        # 카테고리 베스트 (1015=홈인테리어, 1013=주방용품, 1014=생활용품)
  python3 market.py trend "수저통" "식기건조대"       # 네이버 검색량 추이(최근 12주, 상대값)

환경 변수:
  COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY   — 쿠팡 파트너스 > 추가기능 > 오픈 API
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET     — developers.naver.com 애플리케이션 (데이터랩 검색어트렌드)
  NAVER_API_HUB=1                          — 위 키를 네이버 클라우드 API HUB에서 발급했을 때만
"""
import datetime as dt
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import http  # noqa: E402

CP_HOST = "https://api-gateway.coupang.com"
CP_BASE = "/v2/providers/affiliate_open_api/apis/openapi/v1"


def _need(*names):
    miss = [n for n in names if not os.environ.get(n)]
    if miss:
        raise SystemExit(f"환경 변수가 필요합니다: {', '.join(miss)}")


def coupang(method, path, query="", body=None):
    _need("COUPANG_ACCESS_KEY", "COUPANG_SECRET_KEY")
    ak, sk = os.environ["COUPANG_ACCESS_KEY"], os.environ["COUPANG_SECRET_KEY"]
    signed = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    sig = hmac.new(sk.encode(), (signed + method + path + query).encode(), hashlib.sha256).hexdigest()
    auth = f"CEA algorithm=HmacSHA256, access-key={ak}, signed-date={signed}, signature={sig}"
    url = CP_HOST + path + (("?" + query) if query else "")
    data = json.dumps(body).encode() if body is not None else None
    st, raw = http(url, data=data, method=method,
                   headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"})
    out = json.loads(raw or b"{}")
    if st != 200 or str(out.get("rCode", "0")) != "0":
        raise SystemExit(f"쿠팡 API 실패 ({st}): {out}")
    return out.get("data")


def _show(items):
    for i, p in enumerate(items, 1):
        img = (p.get("productImage") or "").replace("230x230ex", "492x492ex")
        print(f"{i}. {p.get('productName')}\n   {p.get('productPrice'):,}원"
              f"{' · 🚀로켓' if p.get('isRocket') else ''}{' · 무료배송' if p.get('isFreeShipping') else ''}"
              f" · 순위 {p.get('rank', '-')}\n   링크 {p.get('productUrl')}\n   이미지 {img}")


def search(keyword, limit=10):
    q = urllib.parse.urlencode({"keyword": keyword, "limit": limit})
    d = coupang("GET", f"{CP_BASE}/products/search", q)
    _show(d.get("productData", []) if isinstance(d, dict) else d)


def goldbox():
    _show(coupang("GET", f"{CP_BASE}/products/goldbox"))


def best(category_id, limit=20):
    _show(coupang("GET", f"{CP_BASE}/products/bestcategories/{category_id}", urllib.parse.urlencode({"limit": limit})))


def deeplink(*urls):
    for d in coupang("POST", f"{CP_BASE}/deeplink", body={"coupangUrls": list(urls)}):
        print(d.get("originalUrl"), "→", d.get("shortenUrl"))


def trend(*keywords):
    _need("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")
    end = dt.date.today()
    start = end - dt.timedelta(weeks=12)
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "week",
            "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords[:5]]}
    cid, secret = os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"]
    if os.environ.get("NAVER_API_HUB"):   # 네이버 클라우드 API HUB에서 발급한 키
        url = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
        hdr = {"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": secret}
    else:                                  # 네이버 개발자센터(developers.naver.com)에서 발급한 키
        url = "https://openapi.naver.com/v1/datalab/search"
        hdr = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    st, raw = http(url, data=json.dumps(body).encode(), method="POST", headers={**hdr, "Content-Type": "application/json"})
    out = json.loads(raw or b"{}")
    if st != 200:
        raise SystemExit(f"네이버 데이터랩 실패 ({st}): {out}")
    for r in out["results"]:
        vals = [round(x["ratio"]) for x in r["data"]]
        bars = "".join("▁▂▃▄▅▆▇█"[min(7, v * 8 // 101)] for v in vals)
        delta = (sum(vals[-3:]) / 3) - (sum(vals[:3]) / 3) if len(vals) >= 6 else 0
        print(f"{r['title']:<12} {bars}  최근 {vals[-1] if vals else 0} ({'↑' if delta > 5 else '↓' if delta < -5 else '→'}{abs(round(delta))})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    cmd, rest = a[0], a[1:]
    {"coupang": lambda: search(" ".join(rest)), "goldbox": goldbox,
     "best": lambda: best(rest[0]), "deeplink": lambda: deeplink(*rest),
     "trend": lambda: trend(*rest)}.get(cmd, lambda: (_ for _ in ()).throw(SystemExit(__doc__)))()
