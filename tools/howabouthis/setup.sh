#!/usr/bin/env bash
# 새 클라우드 세션에서 한 번: 폰트(Pretendard)·Pillow 설치. 이미 있으면 건너뜀.
set -e
if ! fc-list | grep -q "Pretendard"; then
  mkdir -p ~/.fonts && cd /tmp
  curl -sSfL -o pretendard.zip "https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip"
  unzip -q -o pretendard.zip "public/static/*.otf" -d pretendard && cp pretendard/public/static/Pretendard-*.otf ~/.fonts/
  rm -rf pretendard pretendard.zip && fc-cache -f >/dev/null
fi
python3 -c "import PIL" 2>/dev/null || pip install -q pillow 2>/dev/null
command -v ffmpeg >/dev/null || echo "⚠️ ffmpeg 없음 (영상 장면 추출 불가)"
echo "준비 완료: Pretendard $(fc-list | grep -c Pretendard)종, Pillow OK"
