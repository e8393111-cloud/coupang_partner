#!/usr/bin/env python3
"""배관 테스트: 더미 클립 2개 -> 한글 자막 overlay -> 이어붙이기 -> 9:16 MP4."""
import subprocess, os, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
W, H = 1080, 1920
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "test_render.mp4")
TMP = "/tmp/claude-0/-home-user-coupang-partner/243228ff-809e-5136-a361-378ec2a99e30/scratchpad"
os.makedirs(TMP, exist_ok=True)

def make_caption_png(text, path, fontsize=58):
    """하단 반투명 바 + 흰 글자(검은 외곽선) 자막 PNG."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, fontsize)
    # 줄바꿈(간단): 폭 넘으면 두 줄
    def wrap(t):
        if d.textlength(t, font=font) <= W - 120:
            return [t]
        words = t.split(" ")
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if d.textlength(trial, font=font) <= W - 120:
                cur = trial
            else:
                lines.append(cur); cur = w
        if cur: lines.append(cur)
        return lines
    lines = wrap(text)
    lh = fontsize + 18
    block_h = lh * len(lines)
    y0 = int(H * 0.72)
    # 반투명 바
    d.rectangle([0, y0 - 30, W, y0 + block_h + 30], fill=(0, 0, 0, 140))
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        x = (W - tw) / 2
        y = y0 + i * lh
        d.text((x, y), ln, font=font, fill=(255, 255, 255, 255),
               stroke_width=4, stroke_fill=(0, 0, 0, 255))
    img.save(path)

def make_segment(bg_color, caption, out_path, dur=3):
    cap_png = os.path.join(TMP, "cap_" + os.path.basename(out_path) + ".png")
    make_caption_png(caption, cap_png)
    cmd = [FF, "-y",
           "-f", "lavfi", "-i", f"color=c={bg_color}:s={W}x{H}:d={dur}",
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-i", cap_png,
           "-filter_complex", "[0:v][2:v]overlay=0:0[v]",
           "-map", "[v]", "-map", "1:a",
           "-t", str(dur), "-r", "30",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
           out_path]
    subprocess.run(cmd, check=True, capture_output=True)

segs = [
    ("0x101418", "테스트 자막 · 한글 렌더 확인", os.path.join(TMP, "segA.mp4")),
    ("0x1a1030", "구석에 뒀더니 모기가 나 대신 여기로", os.path.join(TMP, "segB.mp4")),
]
for color, cap, path in segs:
    make_segment(color, cap, path)
    print("segment ok:", os.path.basename(path))

# concat
listfile = os.path.join(TMP, "list.txt")
with open(listfile, "w") as f:
    for _, _, path in segs:
        f.write(f"file '{path}'\n")
subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                "-c", "copy", OUT], check=True, capture_output=True)
print("FINAL:", os.path.abspath(OUT))
print("size:", os.path.getsize(OUT), "bytes")
