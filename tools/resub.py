#!/usr/bin/env python3
"""원본 자막 가리고 VO 싱크 맞춘 새 자막 + VO(1.5x) 합성."""
import subprocess, imageio_ffmpeg, re, os
from PIL import Image, ImageDraw, ImageFont
FF = imageio_ffmpeg.get_ffmpeg_exe()
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
TMP = "/tmp/claude-0/-home-user-coupang-partner/243228ff-809e-5136-a361-378ec2a99e30/scratchpad"
VID = "/home/user/coupang_partner/assets/mirra_cleaned.mp4"
OUT = "/home/user/coupang_partner/assets/mirra_final.mp4"
W, H = 1080, 1920
BAR_Y0, BAR_Y1 = 1060, 1740   # 원본 자막 가리는 하단 바 영역

def dur(p):
    r = subprocess.run([FF, "-i", p], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    h, mn, s = m.groups(); return int(h)*3600+int(mn)*60+float(s)

vo_fast = f"{TMP}/vo_fast.m4a"  # 이미 생성됨
adur, vdur = dur(vo_fast), dur(VID)
pad = max(0.0, adur - vdur + 0.25)

# (자막문구, 시작, 끝)  — silencedetect 기반 구간
caps = [
    ("여름철 모기 때문에 밤마다 스트레스…", 0.0, 2.95),
    ("이거 하나만 켜두면 돼요", 2.95, 4.75),
    ("모기가 불빛 따라 모여서 알아서 처리", 4.75, 8.10),
    ("집에서도 캠핑에서도 어디든 · 무선 충전식", 8.10, 11.35),
    ("26,000원 · 내일 로켓배송", 11.35, 14.74),
    ("프로필 링크에서 확인하세요", 14.74, adur + 0.5),
]

def wrap(draw, text, font, maxw):
    if draw.textlength(text, font=font) <= maxw: return [text]
    out, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw: cur = t
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out

def make_png(text, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 상단 바(불투명, 끝까지) — 원본 배너/워터마크·색띠 가림 + 공정위 문구 상시 노출
    TOP = 300
    d.rectangle([0, 0, W, TOP], fill=(12, 14, 20, 255))
    disc = "쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다"
    dfont = ImageFont.truetype(FONT, 36)
    dlines = wrap(d, disc, dfont, W - 70)
    dlh = 46
    dy = (TOP - dlh * len(dlines)) // 2
    for i, ln in enumerate(dlines):
        tw = d.textlength(ln, font=dfont)
        d.text(((W - tw) / 2, dy + i * dlh), ln, font=dfont, fill=(205, 208, 215, 255))
    # 하단 바(불투명, 화면 끝까지) — 원본 자막·색띠 완전 가림
    d.rectangle([0, BAR_Y0, W, H], fill=(12, 14, 20, 255))
    font = ImageFont.truetype(FONT, 60)
    lines = wrap(d, text, font, W - 120)
    lh = 76
    total = lh * len(lines)
    cy = (BAR_Y0 + BAR_Y1) // 2 - total // 2
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        d.text(((W - tw) / 2, cy + i * lh), ln, font=font, fill=(255, 255, 255, 255),
               stroke_width=3, stroke_fill=(0, 0, 0, 255))
    img.save(path)

pngs = []
for i, (txt, a, b) in enumerate(caps):
    p = f"{TMP}/cap{i}.png"; make_png(txt, p); pngs.append(p)

# ffmpeg: 영상 pad → 자막 순차 overlay → VO
inputs = ["-i", VID, "-i", vo_fast]
for p in pngs: inputs += ["-i", p]
fc = [f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.2f}[v0]"]
prev = "v0"
for i, (txt, a, b) in enumerate(caps):
    idx = i + 2
    nxt = f"v{i+1}"
    fc.append(f"[{prev}][{idx}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[{nxt}]")
    prev = nxt
filt = ";".join(fc)
subprocess.run([FF, "-y", *inputs, "-filter_complex", filt,
                "-map", f"[{prev}]", "-map", "1:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", OUT], check=True, capture_output=True)
print(f"video={vdur:.2f} vo={adur:.2f} pad={pad:.2f}")
print("FINAL:", OUT, os.path.getsize(OUT), "bytes", "dur", round(dur(OUT), 2))
