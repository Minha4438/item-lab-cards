"""레퍼런스 계정에서 '지금 반응 터지는 제품' 후보를 뽑는다.

  python3 tools/howabouthis/scout.py            # refs.json의 계정 전부
  python3 tools/howabouthis/scout.py --top 15

점수 = 그 계정 평소 댓글 수(중앙값) 대비 몇 배인지(키워드 댓글 = 구매 관심) × 최신성 × 니치 가중치.
결과: work/scout/<날짜>/candidates.json, 표지 이미지(img/), 한눈에 보기(sheet.jpg)
"""
import argparse
import datetime as dt
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import TOOL_DIR, WORK_DIR, HISTORY, http, load_json, public_profile, save_json  # noqa: E402

KW_RE = re.compile(r"[‘'\"“’\[]\s*([^‘’'\"“”\[\]\s][^‘’'\"“”\[\]]{0,11}?)\s*[’'\"”\]]\s*(?:을|를|이라고|라고)?\s*(?:남겨|댓글|적어|써)")


def caption_of(n):
    e = n["edge_media_to_caption"]["edges"]
    return e[0]["node"]["text"] if e else ""


def cta_keyword(cap):
    m = KW_RE.search(cap)
    return m.group(1).strip() if m else None


def summary_lines(cap, k=3):
    lines = [l.strip() for l in cap.splitlines() if l.strip() and not l.strip().startswith("#")]
    lines = [l for l in lines if not KW_RE.search(l) and "프로필" not in l and "DM" not in l]
    return " / ".join(lines[:k])[:220]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--accounts", nargs="*", help="refs.json 대신 이 계정들만")
    args = ap.parse_args()

    cfg = load_json(os.path.join(TOOL_DIR, "refs.json"))
    accounts = [{"handle": h, "weight": 1.0} for h in args.accounts] if args.accounts else cfg["accounts"]
    niche = cfg.get("niche_keywords", [])
    lookback = cfg.get("lookback_days", 21)
    posted = {(h.get("keyword") or "").strip() for h in load_json(HISTORY, [])} - {""}
    posted_products = [h.get("product", "") for h in load_json(HISTORY, [])]

    today = dt.date.today().isoformat()
    out_dir = os.path.join(WORK_DIR, "scout", today)
    os.makedirs(os.path.join(out_dir, "img"), exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).timestamp()

    cands, errors = [], []
    for acc in accounts:
        h = acc["handle"]
        print(f"@{h} 수집 중…", flush=True)
        try:
            u = public_profile(h)
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)); print("  ", e); continue
        posts = [e["node"] for e in u["edge_owner_to_timeline_media"]["edges"]]
        med = statistics.median([p["edge_media_to_comment"]["count"] for p in posts] or [1]) or 1
        for p in posts:
            age_d = (now - p["taken_at_timestamp"]) / 86400
            pinned = bool(p.get("pinned_for_users"))
            if age_d > lookback and not pinned:
                continue
            cap = caption_of(p)
            kw = cta_keyword(cap)
            if not kw:          # 제품 CTA 없는 글(뉴스·이벤트 등)은 제외
                continue
            cmts, likes = p["edge_media_to_comment"]["count"], p["edge_liked_by"]["count"]
            ratio = cmts / med
            recency = 1.0 if pinned else max(0.35, 1 - age_d / (lookback * 1.4))
            niche_hit = [w for w in niche if w in cap]
            score = acc.get("weight", 1.0) * ratio * recency * (1.3 if niche_hit else 1.0)
            kids = p.get("edge_sidecar_to_children", {}).get("edges", [])
            img_path = os.path.join(out_dir, "img", f"{h}_{p['shortcode']}.jpg")
            if not os.path.exists(img_path):
                st, body = http(p["display_url"])
                if st == 200:
                    open(img_path, "wb").write(body)
            cands.append({
                "score": round(score, 2), "keyword": kw, "account": h,
                "url": f"https://www.instagram.com/p/{p['shortcode']}/",
                "type": {"GraphSidecar": "캐러셀", "GraphVideo": "릴스", "GraphImage": "사진"}.get(p["__typename"], p["__typename"]),
                "slides": len(kids) or 1, "comments": cmts, "likes": likes,
                "views": p.get("video_view_count"), "x_median": round(ratio, 1),
                "age_days": round(age_d, 1), "pinned": pinned, "niche": niche_hit,
                "already_posted": kw in posted or any(kw in pp for pp in posted_products),
                "summary": summary_lines(cap), "caption": cap, "cover": img_path,
            })
        print(f"  게시물 {len(posts)}개, 평소 댓글 중앙값 {med}", flush=True)

    cands.sort(key=lambda c: -c["score"])
    save_json(os.path.join(out_dir, "candidates.json"), {"date": today, "errors": errors, "candidates": cands})

    top = cands[: args.top]
    try:
        from PIL import Image, ImageDraw
        w, hgt = 270, 338
        cols = 4
        sheet = Image.new("RGB", (w * cols, hgt * ((len(top) + cols - 1) // cols or 1)), "white")
        for i, c in enumerate(top):
            if os.path.exists(c["cover"]):
                im = Image.open(c["cover"]).convert("RGB")
                im = im.resize((w, int(w * im.height / im.width))).crop((0, 0, w, hgt))
                d = ImageDraw.Draw(im)
                d.rectangle((0, 0, 44, 30), fill="black"); d.text((8, 8), f"#{i + 1}", fill="white")
                sheet.paste(im, ((i % cols) * w, (i // cols) * hgt))
        sheet.save(os.path.join(out_dir, "sheet.jpg"), quality=85)
    except ImportError:
        pass

    print(f"\n후보 {len(cands)}개 → {out_dir}/candidates.json  (한눈에: sheet.jpg)\n")
    print("| # | 점수 | 키워드 | 계정 | 형식 | 댓글(평소×) | 경과일 | 니치 | 요약 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, c in enumerate(top, 1):
        flag = " ⚠️이미 올림" if c["already_posted"] else (" 📌고정" if c["pinned"] else "")
        print(f"| {i} | {c['score']} | {c['keyword']}{flag} | @{c['account']} | {c['type']} | "
              f"{c['comments']} (×{c['x_median']}) | {c['age_days']} | {','.join(c['niche']) or '-'} | {c['summary'][:70]} |")
    if errors:
        print("\n수집 실패:", *errors, sep="\n- ")


if __name__ == "__main__":
    main()
