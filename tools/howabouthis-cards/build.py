# 이거 어때?(@how.abouthis) 카드뉴스 시안 A/B 생성 — HTML을 만들고 render.js가 1080x1350 PNG로 찍음
import json, os, html
D = os.path.dirname(os.path.abspath(__file__))

KEYWORD = "수저"
slides = [
    # (이미지, 굵은 첫줄, 둘째줄)
    ("f15", None, None),
    ("f13", "설거지하고 수저 꽂아두면", "바닥에 물 고여서 매번 뒤집어 버렸잖아요 ㅠ"),
    ("p1",  "포인트는 바닥의 기울어진 받침!", "물이 받침을 타고 싱크대로 쪼르륵 빠져요"),
    ("f16", "씻고 물기째 바로 꽂아도 OK", "물을 부어봐도 통 안에 안 남더라고요"),
    ("f20", "받침은 2가지 타입이라", "배수형·물받이형 중 자리에 맞춰 끼우면 끝"),
    ("f11", None, None),
]
COVER = dict(eyebrow="설거지 끝나고 수저통 뒤집는 사람 주목",
             l1="수저통에 고인 물", l2="아직도 버려요?",
             sub="꽂아만 두면 알아서 싱크대로 빠지는 수저통 🚰")
N = len(slides)

FONT = "font-family:'Pretendard',sans-serif;"
BASE = """<!doctype html><html><head><meta charset=utf-8><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden;font-family:'Pretendard','Noto Color Emoji',sans-serif;letter-spacing:-0.02em;word-break:keep-all}
.bg{position:absolute;inset:0;background-size:cover;background-position:center}
.ad{position:absolute;top:44px;right:48px;font-size:26px;font-weight:600;color:#fff;background:rgba(0,0,0,.38);padding:6px 14px;border-radius:10px}
%s</style></head><body>%s</body></html>"""

# 말풍선+물음표 로고 (이거 어때?)
def logo(size=64, fill="#FFE14D", ink="#161616"):
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 64 64"><path d="M32 4C16.5 4 4 14.6 4 27.7c0 7.6 4.2 14.3 10.8 18.6L12 58l13.3-7.6c2.2.4 4.4.6 6.7.6 15.5 0 28-10.6 28-23.3S47.5 4 32 4z" fill="{fill}"/><text x="32" y="40" text-anchor="middle" font-family="Pretendard" font-weight="900" font-size="30" fill="{ink}">?</text></svg>'''

def img(name): return f"file://{D}/img/{name}.jpg"

# ───────────────────────── 시안 A: 톡 버블 ─────────────────────────
CSS_A = """
.grad{position:absolute;left:0;right:0;bottom:0;height:62%;background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,.55) 55%,rgba(0,0,0,.78) 100%)}
.tag{position:absolute;left:64px;top:48px;display:flex;align-items:center;gap:10px;background:#FFE14D;color:#161616;font-weight:800;font-size:30px;padding:10px 22px 10px 12px;border-radius:999px;transform:rotate(-3deg);box-shadow:0 6px 18px rgba(0,0,0,.18)}
.tag svg{display:block}
.cover{position:absolute;left:64px;right:64px;bottom:120px;color:#fff}
.eyebrow{font-size:34px;font-weight:600;opacity:.92;margin-bottom:22px}
.h{font-size:98px;line-height:1.16;font-weight:900}
.mark{display:inline;background:#FFE14D;color:#161616;padding:0 14px;box-decoration-break:clone;-webkit-box-decoration-break:clone;border-radius:10px}
.sub{margin-top:30px;font-size:36px;font-weight:500;opacity:.95}
.page{position:absolute;right:56px;bottom:48px;color:#fff;font-size:26px;font-weight:700;opacity:.85}
.handle{position:absolute;left:64px;bottom:48px;color:#fff;font-size:26px;font-weight:600;opacity:.85}
.chat{position:absolute;left:56px;right:56px;bottom:110px;display:flex;align-items:flex-end;gap:16px}
.av{flex:none;width:84px;height:84px;border-radius:50%;background:#161616;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 16px rgba(0,0,0,.25)}
.bub{position:relative;background:#fff;border-radius:40px 40px 40px 10px;padding:32px 40px;box-shadow:0 10px 30px rgba(0,0,0,.22);color:#222}
.bub .b1{font-size:40px;font-weight:800;line-height:1.35}
.bub .b1 span{background:linear-gradient(transparent 58%,#FFE14D 58%)}
.bub .b2{margin-top:8px;font-size:34px;font-weight:500;line-height:1.45;color:#444}
.shade{position:absolute;left:0;right:0;bottom:0;height:45%;background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.35))}
.dim{position:absolute;inset:0;background:rgba(0,0,0,.52)}
.cta{position:absolute;left:64px;right:64px;top:300px;color:#fff;text-align:center}
.cta .q{font-size:44px;font-weight:600;opacity:.95}
.cta .big{margin-top:18px;font-size:88px;font-weight:900;line-height:1.2}
.input{position:absolute;left:64px;right:64px;top:720px;height:118px;background:#fff;border-radius:999px;display:flex;align-items:center;padding:0 18px 0 22px;gap:20px;box-shadow:0 14px 40px rgba(0,0,0,.3)}
.input .me{width:78px;height:78px;border-radius:50%;background:#e9e9e9}
.input .txt{flex:1;font-size:44px;font-weight:800;color:#161616}
.input .txt i{font-style:normal;display:inline-block;width:4px;height:46px;background:#161616;vertical-align:-8px;margin-left:6px}
.input .send{font-size:34px;font-weight:800;color:#3a7cff}
.note{position:absolute;left:64px;right:64px;top:880px;color:#fff;text-align:center;font-size:32px;line-height:1.6;text-shadow:0 2px 10px rgba(0,0,0,.5)}
.ptr{position:absolute;left:170px;top:860px;font-size:64px}
"""

def slide_A(i, s):
    name, b1, b2 = s
    ad = '<div class="ad">광고</div>'
    page = f'<div class="page">{i+1} / {N}</div>'
    tag = f'<div class="tag">{logo(46, "#161616", "#FFE14D")}<span>이거 어때?</span></div>'
    if i == 0:
        body = f'''<div class="bg" style="background-image:url({img(name)})"></div><div class="grad"></div>{tag}{ad}
<div class="cover"><div class="eyebrow">{COVER["eyebrow"]} 👀</div>
<div class="h">{COVER["l1"]}<br><span class="mark">{COVER["l2"]}</span></div>
<div class="sub">{COVER["sub"]}</div></div><div class="handle">@how.abouthis</div>{page}'''
    elif i == N - 1:
        body = f'''<div class="bg" style="background-image:url({img(name)})"></div><div class="dim"></div>{tag}{ad}
<div class="cta"><div class="q">그래서, 이거 어때요? 🤔</div><div class="big">제품 정보 궁금하면<br>댓글 한 줄이면 끝</div></div>
<div class="input"><div class="av" style="width:78px;height:78px">{logo(54)}</div><div class="txt">{KEYWORD}<i></i></div><div class="send">게시</div></div>
<div class="note">댓글에 <b>‘{KEYWORD}’</b> 남기면 DM으로 바로 보내드려요<br>DM이 안 보이면 요청함도 확인해주세요 🙌</div>
<div class="handle">@how.abouthis</div>{page}'''
    else:
        body = f'''<div class="bg" style="background-image:url({img(name)})"></div><div class="shade"></div>{ad}
<div class="chat"><div class="av">{logo(60)}</div><div class="bub"><div class="b1"><span>{b1}</span></div><div class="b2">{b2}</div></div></div>{page}'''
    return BASE % (CSS_A, body)

# ───────────────────────── 시안 B: 옐로 프레임(매거진) ─────────────────────────
CSS_B = """
body{background:#FFE14D;color:#161616}
.top{position:absolute;left:64px;right:64px;top:52px;display:flex;align-items:center;justify-content:space-between}
.brand{display:flex;align-items:center;gap:12px;font-size:32px;font-weight:900}
.no{font-size:26px;font-weight:700;border:3px solid #161616;border-radius:999px;padding:6px 18px}
.adb{font-size:24px;font-weight:700;opacity:.6;margin-left:14px}
.frame{position:absolute;left:64px;right:64px;border-radius:44px;overflow:hidden;border:5px solid #161616;background-size:cover;background-position:center}
.ch{position:absolute;left:64px;right:64px;top:150px}
.ch .k{font-size:34px;font-weight:700;margin-bottom:14px}
.ch .h{font-size:84px;line-height:1.14;font-weight:900}
.ch .h u{text-decoration:none;background:#161616;color:#FFE14D;padding:0 12px;border-radius:10px}
.sticker{position:absolute;right:92px;top:520px;width:200px;height:200px;border-radius:50%;background:#FF5A36;color:#fff;font-weight:900;font-size:34px;line-height:1.2;display:flex;align-items:center;justify-content:center;text-align:center;transform:rotate(10deg);box-shadow:0 8px 0 #161616;border:5px solid #161616}
.foot{position:absolute;left:64px;right:64px;bottom:44px;display:flex;justify-content:space-between;font-size:26px;font-weight:700}
.num{position:absolute;left:64px;top:150px;font-size:120px;font-weight:900;line-height:1;-webkit-text-stroke:4px #161616;color:transparent}
.cap{position:absolute;left:64px;right:64px;bottom:128px}
.cap .b1{font-size:52px;font-weight:900;line-height:1.3}
.cap .b2{margin-top:12px;font-size:36px;font-weight:600;line-height:1.45;opacity:.82}
.cta{position:absolute;left:64px;right:64px;top:170px}
.cta .q{font-size:40px;font-weight:800}
.cta .big{margin-top:14px;font-size:96px;font-weight:900;line-height:1.15}
.kw{display:inline-block;background:#161616;color:#FFE14D;padding:2px 26px 8px;border-radius:24px;transform:rotate(-2deg)}
.cta .s{margin-top:28px;font-size:34px;font-weight:600;line-height:1.55;opacity:.85}
"""

def slide_B(i, s):
    name, b1, b2 = s
    top = f'<div class="top"><div class="brand">{logo(56, "#161616", "#FFE14D")}이거 어때?</div><div style="display:flex;align-items:center"><div class="no">살림템 No.01</div><div class="adb">광고</div></div></div>'
    foot = f'<div class="foot"><span>@how.abouthis</span><span>{i+1} / {N}</span></div>'
    if i == 0:
        body = f'''{top}<div class="ch"><div class="k">{COVER["eyebrow"]} 👀</div><div class="h">{COVER["l1"]}<br><u>{COVER["l2"]}</u></div></div>
<div class="frame" style="top:470px;bottom:110px;background-image:url({img(name)})"></div>
<div class="sticker">꽂으면<br>물이<br>빠진다!</div>{foot}'''
    elif i == N - 1:
        body = f'''{top}<div class="cta"><div class="q">그래서, 이거 어때요? 🤔</div>
<div class="big">댓글에<br><span class="kw">‘{KEYWORD}’</span><br>남겨주세요</div>
<div class="s">제품 정보 DM으로 바로 보내드려요<br>DM이 안 보이면 요청함도 확인 🙌</div></div>
<div class="frame" style="top:800px;bottom:120px;left:520px;right:80px;background-image:url({img(name)});transform:rotate(4deg)"></div>{foot}'''
    else:
        body = f'''{top}<div class="frame" style="top:150px;bottom:350px;background-image:url({img(name)})"></div>
<div class="cap"><div class="b1">{b1}</div><div class="b2">{b2}</div></div>{foot}'''
    return BASE % (CSS_B, body)

jobs = []
for tag, fn in [("A", slide_A), ("B", slide_B)]:
    os.makedirs(f"{D}/html/{tag}", exist_ok=True); os.makedirs(f"{D}/out/{tag}", exist_ok=True)
    for i, s in enumerate(slides):
        p = f"{D}/html/{tag}/{i+1:02d}.html"
        open(p, "w").write(fn(i, s))
        jobs.append([p, f"{D}/out/{tag}/{i+1:02d}.png"])
json.dump(jobs, open(f"{D}/jobs.json", "w"))
print(len(jobs), "slides")
