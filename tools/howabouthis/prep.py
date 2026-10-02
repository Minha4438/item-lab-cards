"""카드에 쓸 사진 준비.

  python3 prep.py own-reel <폴더> [--index 0 | --shortcode Dd6OLNbyTzv]   # 내 계정 릴스에서 장면 추출
  python3 prep.py video <폴더> <영상 URL 또는 파일> [--fps 1]              # 아무 영상에서 장면 추출
  python3 prep.py images <폴더> <이미지 URL 또는 파일> ...                 # 사진 내려받기/복사
  python3 prep.py crop <입력> <출력> <x> <y> <w> <h>                      # 자막 등 피해서 잘라내기
  python3 prep.py sheet <폴더>                                            # 번호 붙은 한눈에 보기(sheet.jpg)

추출/다운로드 후 항상 <폴더>/sheet.jpg 를 만든다 — 이걸 보고 장면을 고른다.
"""
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import http, ig_api  # noqa: E402


def sheet(folder):
    from PIL import Image, ImageDraw
    fs = sorted(f for f in glob.glob(os.path.join(folder, "*.jpg")) if not f.endswith("sheet.jpg"))
    if not fs:
        return
    w, cols = 200, 8
    hs = [int(w * Image.open(f).height / Image.open(f).width) for f in fs]
    h = max(hs)
    S = Image.new("RGB", (w * cols, h * ((len(fs) + cols - 1) // cols)), "white")
    for i, f in enumerate(fs):
        im = Image.open(f).convert("RGB")
        im = im.resize((w, int(w * im.height / im.width)))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 90, 22), fill="black"); d.text((4, 5), os.path.basename(f)[:-4], fill="yellow")
        S.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(folder, "sheet.jpg")
    S.save(out, quality=85)
    print("한눈에 보기 →", out)


def frames(folder, src, fps=1.0):
    os.makedirs(folder, exist_ok=True)
    if src.startswith("http"):
        st, body = http(src, timeout=120)
        if st != 200:
            raise SystemExit(f"영상 다운로드 실패 {st}")
        src = os.path.join(folder, "_video.mp4")
        open(src, "wb").write(body)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"fps={fps}", "-q:v", "2",
                    os.path.join(folder, "fr%02d.jpg")], check=True)
    print(f"장면 {len(glob.glob(os.path.join(folder, 'fr*.jpg')))}개 추출")
    sheet(folder)


def own_reel(folder, index=0, shortcode=None):
    media = ig_api("me/media", {"fields": "id,media_type,media_url,permalink,caption,timestamp", "limit": 25})["data"]
    vids = [m for m in media if m["media_type"] == "VIDEO"]
    if shortcode:
        vids = [m for m in vids if shortcode in m["permalink"]]
    if not vids:
        raise SystemExit("해당 릴스를 찾지 못함")
    m = vids[index if not shortcode else 0]
    print("릴스:", m["permalink"], "|", (m.get("caption") or "")[:40].replace("\n", " "))
    if "media_url" not in m:
        raise SystemExit("이 릴스는 API로 영상 원본을 받을 수 없음(저작권 음원 등). 원본 영상/사진을 따로 주세요.")
    frames(folder, m["media_url"])


def images(folder, srcs):
    os.makedirs(folder, exist_ok=True)
    for i, s in enumerate(srcs, 1):
        dst = os.path.join(folder, f"im{i:02d}.jpg")
        if s.startswith("http"):
            st, body = http(s, timeout=60)
            if st != 200:
                print("실패:", s, st); continue
            open(dst + ".tmp", "wb").write(body)
        else:
            shutil.copy(s, dst + ".tmp")
        from PIL import Image
        Image.open(dst + ".tmp").convert("RGB").save(dst, quality=94)
        os.remove(dst + ".tmp")
    sheet(folder)


def crop(src, dst, x, y, w, h):
    from PIL import Image
    Image.open(src).convert("RGB").crop((x, y, x + w, y + h)).save(dst, quality=94)
    print("→", dst)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    cmd = a[0]
    if cmd == "own-reel":
        idx = int(a[a.index("--index") + 1]) if "--index" in a else 0
        sc = a[a.index("--shortcode") + 1] if "--shortcode" in a else None
        own_reel(a[1], idx, sc)
    elif cmd == "video":
        fps = float(a[a.index("--fps") + 1]) if "--fps" in a else 1.0
        frames(a[1], a[2], fps)
    elif cmd == "images":
        images(a[1], a[2:])
    elif cmd == "crop":
        crop(a[1], a[2], *map(int, a[3:7]))
    elif cmd == "sheet":
        sheet(a[1])
    else:
        raise SystemExit(__doc__)
