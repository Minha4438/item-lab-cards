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


GONGGU_RE = re.compile(r"[\[🧡]\s*([^\]\n]{2,30}?)\s*\]?\s*공구\s*(?:예고|오픈|OPEN)")


def cta_keyword(cap):
    m = KW_RE.search(cap)
    return m.group(1).strip() if m else None


def gonggu_name(cap):
    """공구 계정의 '[제품명] 공구예고' 글 — 키워드 CTA는 없지만 오픈 전 수요 신호라 후보로 본다."""
    m = GONGGU_RE.search(cap)
    return f"공구:{m.group(1).strip()}" if m else None


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
        posts = u["posts"]
        med = statistics.median([p["comments"] for p in posts] or [1]) or 1
        for p in posts:
            age_d = (now - p["ts"]) / 86400
            if age_d > lookback and not p["pinned"]:
                continue
            cap = p["caption"]
            kw = cta_keyword(cap) or gonggu_name(cap)
            if not kw:          # 제품 CTA 없는 글(뉴스·이벤트 등)은 제외
                continue
            ratio = p["comments"] / med
            recency = max(0.35, 1 - age_d / (lookback * 1.4)) if age_d <= lookback else 0.15  # 오래된 고정글은 따로 표시
            niche_hit = [w for w in niche if w in cap]
            score = acc.get("weight", 1.0) * ratio * recency * (1.3 if niche_hit else 1.0)
            img_path = os.path.join(out_dir, "img", f"{h}_{p['shortcode']}.jpg")
            if p.get("image") and not os.path.exists(img_path):
                st, body = http(p["image"])
                if st == 200:
                    open(img_path, "wb").write(body)
            cands.append({
                "score": round(score, 2), "keyword": kw, "account": h, "url": p["url"], "type": p["type"],
                "slides": p["slides"], "comments": p["comments"], "likes": p["likes"], "views": p["views"],
                "x_median": round(ratio, 1), "age_days": round(age_d, 1), "pinned": p["pinned"], "niche": niche_hit,
                "already_posted": kw in posted or any(kw in pp for pp in posted_products),
                "summary": summary_lines(cap), "caption": cap, "cover": img_path,
            })
        print(f"  게시물 {len(posts)}개, 평소 댓글 중앙값 {med}", flush=True)

    cands.sort(key=lambda c: -c["score"])
    

    steady = [c for c in cands if c["age_days"] > lookback]
    cands = [c for c in cands if c["age_days"] <= lookback]
    top = cands[: args.top]
    save_json(os.path.join(out_dir, "candidates.json"), {"date": today, "errors": errors, "candidates": cands, "steady": steady})
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
    if steady:
        print("\n📌 오래됐지만 고정해둔 스테디셀러 (검증된 아이템):")
        for c in steady:
            print(f"- {c['keyword']} @{c['account']} 댓글 {c['comments']} (평소×{c['x_median']}, {int(c['age_days'])}일 전) — {c['summary'][:60]}")
    if errors:
        print("\n수집 실패:", *errors, sep="\n- ")


if __name__ == "__main__":
    main()
