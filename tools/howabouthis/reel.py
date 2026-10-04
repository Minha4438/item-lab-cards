"""렌더된 카드(out/*.jpg)를 슬라이드 릴스(1080x1920 MP4)로 만든다.

  python3 tools/howabouthis/reel.py work/cards/<id>/spec.json
  python3 tools/howabouthis/reel.py work/cards/<id>/spec.json --sec 2.5 --cover-sec 3 --audio bgm.mp3

결과: work/cards/<id>/reel.mp4, reel_preview.jpg(프레임 모음)
- 4:5 카드를 9:16 화면 위쪽에 두고, 남는 위아래는 그 장의 원본 사진(글씨 없음)을 흐리게 깔아 채운다.
  릴스 하단(아이디·캡션·버튼 영역)에 카드 글씨가 가리지 않도록 카드를 살짝 줄여 위로 올린다.
- 장 사이 0.4초 크로스페이드. 음원이 없으면 무음 트랙(인스타 호환용).
- 음원은 저작권 없는 파일만 (인스타 음악 라이브러리는 API로 못 붙임 — 필요하면 앱에서 직접 추가).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_json  # noqa: E402

W, H = 1080, 1920
CARD_W = 1000            # 1080x1350 카드를 1000x1250으로
CARD_TOP = 230           # 위 230px(상단 UI) · 아래 440px(하단 UI) 비움
FADE = 0.4
FPS = 30


def frame(card_path, photo_path, out_path):
    from PIL import Image, ImageEnhance, ImageFilter
    card = Image.open(card_path).convert("RGB")
    src = Image.open(photo_path).convert("RGB") if photo_path and os.path.exists(photo_path) else card
    scale = max(W / src.width, H / src.height)         # 화면을 꽉 채우게 키운 뒤 가운데만
    bw, bh = round(src.width * scale), round(src.height * scale)
    bg = src.resize((bw, bh)).crop(((bw - W) // 2, (bh - H) // 2, (bw - W) // 2 + W, (bh - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(40))).enhance(0.6)
    fg = card.resize((CARD_W, round(card.height * CARD_W / card.width)), Image.LANCZOS)
    bg.paste(fg, ((W - CARD_W) // 2, CARD_TOP))
    bg.save(out_path, quality=95)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--sec", type=float, default=2.5, help="본문 한 장당 초")
    ap.add_argument("--cover-sec", type=float, default=3.0, help="표지 초 (첫 장)")
    ap.add_argument("--audio", help="배경 음원 파일 (저작권 없는 것만)")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(args.spec))
    spec = load_json(args.spec)
    cards = sorted(glob.glob(os.path.join(base, "out", "*.jpg")))
    if len(cards) < 2:
        raise SystemExit("out/*.jpg 가 2장 이상 필요 — cards.py 로 먼저 렌더")
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg 없음")

    # out/NN.jpg 순서 = 표지, 본문들, CTA → 같은 순서의 원본 사진을 배경으로
    photos = [spec.get("cover", {}).get("image")] + [s.get("image") for s in spec.get("slides", [])] \
        + [spec.get("cta", {}).get("image")]
    photos = [os.path.join(base, p) if p else None for p in photos]
    if len(photos) != len(cards):
        photos = [None] * len(cards)

    tmp = tempfile.mkdtemp()
    frames = []
    for i, (c, ph) in enumerate(zip(cards, photos)):
        p = os.path.join(tmp, f"{i:02d}.jpg")
        frame(c, ph, p)
        frames.append(p)
    durs = [args.cover_sec] + [args.sec] * (len(frames) - 1)
    durs[-1] += 0.5  # 마지막(CTA) 장은 조금 더 길게

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p, d in zip(frames, durs):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.2f}", "-i", p]
    total = sum(durs) - FADE * (len(durs) - 1)
    if args.audio:
        cmd += ["-stream_loop", "-1", "-i", args.audio]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    a_idx = len(frames)

    chains, last, length = [], "[0:v]", durs[0]
    for k in range(1, len(frames)):
        out = f"[x{k}]"
        chains.append(f"{last}[{k}:v]xfade=transition=fade:duration={FADE}:offset={length - FADE:.2f}{out}")
        last, length = out, length + durs[k] - FADE
    chains.append(f"{last}format=yuv420p[v]")
    chains.append(f"[{a_idx}:a]atrim=0:{total:.2f},afade=t=out:st={max(total - 1, 0):.2f}:d=1[a]")
    out_mp4 = os.path.join(base, "reel.mp4")
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20", "-maxrate", "8M", "-bufsize", "12M",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-t", f"{total:.2f}",
            "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)

    # 미리보기: 장마다 가운데 프레임
    from PIL import Image
    thumbs, t = [], 0.0
    for d in durs:
        tp = os.path.join(tmp, f"t{len(thumbs)}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t + d / 2:.2f}", "-i", out_mp4,
                        "-frames:v", "1", "-vf", "scale=270:480", tp], check=True)
        thumbs.append(Image.open(tp))
        t += d - FADE
    sheet = Image.new("RGB", (270 * min(len(thumbs), 5), 480 * ((len(thumbs) + 4) // 5)), "white")
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % 5) * 270, (i // 5) * 480))
    sheet.save(os.path.join(base, "reel_preview.jpg"), quality=85)
    shutil.rmtree(tmp, ignore_errors=True)
    mb = os.path.getsize(out_mp4) / 1e6
    print(f"릴스 {total:.1f}초 · {len(frames)}장 · {mb:.1f}MB → {out_mp4}\n미리보기 → {os.path.join(base, 'reel_preview.jpg')}")


if __name__ == "__main__":
    main()
