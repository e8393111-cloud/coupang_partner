#!/usr/bin/env python3
"""Mirra 초벌 영상 자동 후처리: 배너/워터마크 크롭 제거 + 구간 선택 트림 + 클린 CTA 자막."""
import subprocess, os, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
SRC = "/root/.claude/uploads/243228ff-809e-5136-a361-378ec2a99e30/ab54faaf-81________________.mp4"
TMP = "/tmp/claude-0/-home-user-coupang-partner/243228ff-809e-5136-a361-378ec2a99e30/scratchpad"
OUT = "/home/user/coupang_partner/assets/mirra_cleaned.mp4"
W, H = 1080, 1920

# 상단 배너+워터마크 제거용 크롭(9:16 유지 후 리스케일) + setsar
VF = "crop=1001:1780:39:140,scale=1080:1920,setsar=1"

def cut(ss, dur, out):
    subprocess.run([FF, "-y", "-ss", str(ss), "-t", str(dur), "-i", SRC,
                    "-vf", VF, "-r", "30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "48000", out],
                   check=True, capture_output=True)

# 살릴 구간: 훅(0~3s) + 원리~캠핑(22~34s)
segs = [(0.0, 3.0, f"{TMP}/p1.mp4"), (22.0, 12.0, f"{TMP}/p2.mp4")]
for ss, d, p in segs:
    cut(ss, d, p)
    print("cut ok:", os.path.basename(p))

listf = f"{TMP}/mlist.txt"
open(listf, "w").write("".join(f"file '{p}'\n" for _, _, p in segs))
mid = f"{TMP}/mid.mp4"
subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", listf,
                "-c", "copy", mid], check=True, capture_output=True)
print("concat ok")

# 클린 CTA 자막 PNG (끝 3.5초 노출)
cta = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(cta)
f1 = ImageFont.truetype(FONT, 66)
f2 = ImageFont.truetype(FONT, 54)
line1 = "프로필 링크에서 구매"
line2 = "26,000원 · 로켓배송"
y0 = int(H * 0.60)
d.rectangle([0, y0 - 30, W, y0 + 200], fill=(0, 0, 0, 150))
for txt, fnt, dy in [(line1, f1, 0), (line2, f2, 90)]:
    tw = d.textlength(txt, font=fnt)
    d.text(((W - tw) / 2, y0 + dy), txt, font=fnt, fill=(255, 255, 255, 255),
           stroke_width=4, stroke_fill=(0, 0, 0, 255))
cta_png = f"{TMP}/cta.png"
cta.save(cta_png)

# 마지막 3.5초에 CTA overlay (전체 길이 15s → t>=11.5)
subprocess.run([FF, "-y", "-i", mid, "-i", cta_png,
                "-filter_complex", "[0:v][1:v]overlay=0:0:enable='gte(t,11.5)'[v]",
                "-map", "[v]", "-map", "0:a?",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", OUT],
               check=True, capture_output=True)
print("FINAL:", OUT, os.path.getsize(OUT), "bytes")
