"""spec.json → 시안 A(톡 버블) 카드뉴스 1080x1350 JPG.

  python3 tools/howabouthis/cards.py work/cards/<id>/spec.json
  → work/cards/<id>/out/01.jpg … + preview.jpg(한눈에 보기)

spec 형식은 examples/sujeo/spec.json 참고. 이미지 경로는 spec 파일 기준 상대경로.
이미지 항목은 "파일" 또는 {"src": 파일, "pos": "50% 30%"(초점), "zoom": 1.2}.
"""
import html
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import TOOL_DIR  # noqa: E402

HANDLE = "@how.abouthis"
YELLOW, INK = "#FFE14D", "#161616"


def logo(size=64, fill=YELLOW, ink=INK):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 64 64"><path d="M32 4C16.5 4 4 14.6 4 27.7c0 7.6 4.2 14.3 '
            f'10.8 18.6L12 58l13.3-7.6c2.2.4 4.4.6 6.7.6 15.5 0 28-10.6 28-23.3S47.5 4 32 4z" fill="{fill}"/>'
            f'<text x="32" y="40" text-anchor="middle" font-family="Pretendard" font-weight="900" font-size="30" '
            f'fill="{ink}">?</text></svg>')


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden;font-family:'Pretendard','Noto Color Emoji',sans-serif;letter-spacing:-0.02em;word-break:keep-all;background:#222}
.bg{position:absolute;inset:0;background-size:cover;background-position:center;background-repeat:no-repeat}
.ad{position:absolute;top:44px;right:48px;font-size:26px;font-weight:600;color:#fff;background:rgba(0,0,0,.38);padding:6px 14px;border-radius:10px}
.grad{position:absolute;left:0;right:0;bottom:0;height:62%;background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,.55) 55%,rgba(0,0,0,.8) 100%)}
.tag{position:absolute;left:64px;top:48px;display:flex;align-items:center;gap:10px;background:#FFE14D;color:#161616;font-weight:800;font-size:30px;padding:10px 22px 10px 12px;border-radius:999px;transform:rotate(-3deg);box-shadow:0 6px 18px rgba(0,0,0,.18)}
.tag svg{display:block}
.cover{position:absolute;left:64px;right:64px;bottom:120px;color:#fff}
.eyebrow{font-size:34px;font-weight:600;opacity:.95;margin-bottom:22px;text-shadow:0 2px 8px rgba(0,0,0,.35)}
.h{font-size:98px;line-height:1.16;font-weight:900}
.h>div{white-space:nowrap}
.mark{display:inline-block;background:#FFE14D;color:#161616;padding:0 14px;border-radius:10px;margin-top:4px}
.sub{margin-top:30px;font-size:36px;font-weight:500;opacity:.95}
.page{position:absolute;right:48px;bottom:40px;color:#fff;font-size:24px;font-weight:700;background:rgba(0,0,0,.38);padding:6px 14px;border-radius:999px}
.handle{position:absolute;left:64px;bottom:48px;color:#fff;font-size:26px;font-weight:600;opacity:.9;text-shadow:0 1px 6px rgba(0,0,0,.4)}
.chat{position:absolute;left:56px;right:56px;display:flex;align-items:flex-end;gap:16px}
.chat.bottom{bottom:110px}.chat.top{top:120px}
.av{flex:none;width:84px;height:84px;border-radius:50%;background:#161616;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 16px rgba(0,0,0,.25)}
.bub{position:relative;max-width:840px;background:#fff;border-radius:40px 40px 40px 10px;padding:32px 40px;box-shadow:0 10px 30px rgba(0,0,0,.22);color:#222}
.bub .b1{font-size:40px;font-weight:800;line-height:1.35;white-space:nowrap}
.bub .b1 span{background:linear-gradient(transparent 58%,#FFE14D 58%)}
.bub .b2{margin-top:8px;font-size:34px;font-weight:500;line-height:1.45;color:#444}
.shade{position:absolute;left:0;right:0;height:45%}
.shade.bottom{bottom:0;background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.35))}
.shade.top{top:0;background:linear-gradient(0deg,rgba(0,0,0,0),rgba(0,0,0,.3))}
.dim{position:absolute;inset:0;background:rgba(0,0,0,.52)}
.cta{position:absolute;left:64px;right:64px;top:300px;color:#fff;text-align:center}
.cta .q{font-size:44px;font-weight:600}
.cta .big{margin-top:18px;font-size:88px;font-weight:900;line-height:1.2}
.cta .big>div{white-space:nowrap}
.input{position:absolute;left:64px;right:64px;top:720px;height:118px;background:#fff;border-radius:999px;display:flex;align-items:center;padding:0 30px 0 20px;gap:20px;box-shadow:0 14px 40px rgba(0,0,0,.3)}
.input .txt{flex:1;font-size:44px;font-weight:800;color:#161616;white-space:nowrap}
.input .txt i{font-style:normal;display:inline-block;width:4px;height:46px;background:#161616;vertical-align:-8px;margin-left:6px}
.input .send{font-size:34px;font-weight:800;color:#3a7cff}
.note{position:absolute;left:64px;right:64px;top:880px;color:#fff;text-align:center;font-size:32px;line-height:1.6;text-shadow:0 2px 10px rgba(0,0,0,.5)}
"""

# 글자가 넘치면 줄이는 스크립트 (nowrap 요소의 폭 기준)
FIT_JS = """
<script>
function fit(el, maxW){let fs=parseFloat(getComputedStyle(el).fontSize);while(el.scrollWidth>maxW&&fs>18){fs-=2;el.style.fontSize=fs+'px';}}
document.fonts.ready.then(()=>{
  document.querySelectorAll('[data-fit]').forEach(el=>fit(el, +el.dataset.fit));
  document.body.dataset.ready='1';
});
</script>"""


def esc(s):
    return html.escape(s or "").replace("\n", "<br>")


def bg(img, base):
    if isinstance(img, str):
        img = {"src": img}
    src = os.path.abspath(os.path.join(base, img["src"]))
    if not os.path.exists(src):
        raise SystemExit(f"이미지 없음: {src}")
    pos = img.get("pos", "center")
    size = f"{int(img['zoom'] * 100)}% auto" if img.get("zoom") else "cover"
    return f'<div class="bg" style="background-image:url(\'file://{src}\');background-position:{pos};background-size:{size}"></div>'


def page(body):
    return f"<!doctype html><html><head><meta charset=utf-8><style>{CSS}</style></head><body>{body}{FIT_JS}</body></html>"


def build(spec, base):
    n = 2 + len(spec["slides"])
    ad = '<div class="ad">광고</div>' if spec.get("ad", True) else ""
    tag = f'<div class="tag">{logo(46, INK, YELLOW)}<span>{esc(spec.get("tag", "이거 어때?"))}</span></div>'
    pg = lambda i: f'<div class="page">{i} / {n}</div>'  # noqa: E731
    hd = f'<div class="handle">{HANDLE}</div>'
    pages = []

    c = spec["cover"]
    pages.append(page(f"""{bg(c['image'], base)}<div class="grad"></div>{tag}{ad}
<div class="cover"><div class="eyebrow" data-fit="952" style="white-space:nowrap">{esc(c.get('eyebrow'))}</div>
<div class="h"><div data-fit="952">{esc(c['line1'])}</div><div data-fit="952"><span class="mark">{esc(c['line2'])}</span></div></div>
<div class="sub">{esc(c.get('sub'))}</div></div>{hd}{pg(1)}"""))

    for i, s in enumerate(spec["slides"], 2):
        where = s.get("bubble", "bottom")
        pages.append(page(f"""{bg(s['image'], base)}<div class="shade {where}"></div>{ad}
<div class="chat {where}"><div class="av">{logo(60)}</div><div class="bub"><div class="b1" data-fit="760"><span>{esc(s['bold'])}</span></div>
<div class="b2">{esc(s.get('text'))}</div></div></div>{pg(i)}"""))

    t = spec.get("cta", {})
    kw = spec["keyword"]
    big = t.get("big", "제품 정보 궁금하면\n댓글 한 줄이면 끝").split("\n")
    note = t.get("note", f"댓글에 <b>‘{html.escape(kw)}’</b> 남기면 DM으로 바로 보내드려요<br>DM이 안 보이면 요청함도 확인해주세요 🙌")
    pages.append(page(f"""{bg(t.get('image') or spec['cover']['image'], base)}<div class="dim"></div>{tag}{ad}
<div class="cta"><div class="q">{esc(t.get('q', '그래서, 이거 어때요? 🤔'))}</div><div class="big">{''.join(f'<div data-fit="952">{esc(b)}</div>' for b in big)}</div></div>
<div class="input"><div class="av" style="width:78px;height:78px">{logo(54)}</div><div class="txt">{esc(kw)}<i></i></div><div class="send">게시</div></div>
<div class="note">{note}</div>{hd}{pg(n)}"""))
    return pages


def main():
    spec_path = os.path.abspath(sys.argv[1])
    base = os.path.dirname(spec_path)
    spec = json.load(open(spec_path, encoding="utf-8"))
    if not 3 <= len(spec["slides"]) + 2 <= 10:
        raise SystemExit("캐러셀은 3~10장이어야 합니다 (표지+본문+CTA).")
    pages = build(spec, base)
    hdir, odir = os.path.join(base, "html"), os.path.join(base, "out")
    os.makedirs(hdir, exist_ok=True); os.makedirs(odir, exist_ok=True)
    for f in os.listdir(odir):
        os.remove(os.path.join(odir, f))
    jobs = []
    for i, p in enumerate(pages, 1):
        hp = os.path.join(hdir, f"{i:02d}.html")
        open(hp, "w", encoding="utf-8").write(p)
        jobs.append([hp, os.path.join(odir, f"{i:02d}.png")])
    subprocess.run(["node", os.path.join(TOOL_DIR, "render.js"), json.dumps(jobs)], check=True)

    from PIL import Image
    w, h, cols = 360, 450, min(len(jobs), 4)
    sheet = Image.new("RGB", (w * cols, h * ((len(jobs) + cols - 1) // cols)), "white")
    for i, (_, png) in enumerate(jobs):
        im = Image.open(png).convert("RGB")
        im.save(png[:-4] + ".jpg", quality=92)   # Instagram은 JPEG만 받음
        os.remove(png)
        sheet.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(os.path.join(base, "preview.jpg"), quality=88)
    print(f"{len(jobs)}장 → {odir}\n미리보기 → {os.path.join(base, 'preview.jpg')}")


if __name__ == "__main__":
    main()
