#!/usr/bin/env python3
"""완성본: 영상 원본 음소거 + VO(1.5배) 얹기 + 길이 맞춤(끝 프레임 홀드)."""
import subprocess, imageio_ffmpeg, re, os
FF = imageio_ffmpeg.get_ffmpeg_exe()
TMP = "/tmp/claude-0/-home-user-coupang-partner/243228ff-809e-5136-a361-378ec2a99e30/scratchpad"
VID = "/home/user/coupang_partner/assets/mirra_cleaned.mp4"
VO  = "/home/user/coupang_partner/vo.mp3"
OUT = "/home/user/coupang_partner/assets/mirra_final.mp4"
TEMPO = 1.5

def dur(p):
    r = subprocess.run([FF, "-i", p], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    h, mnt, s = m.groups(); return int(h)*3600 + int(mnt)*60 + float(s)

# 1) VO 1.5배
vo_fast = f"{TMP}/vo_fast.m4a"
subprocess.run([FF, "-y", "-i", VO, "-filter:a", f"atempo={TEMPO}",
                "-c:a", "aac", "-b:a", "160k", vo_fast], check=True, capture_output=True)
adur, vdur = dur(vo_fast), dur(VID)
pad = max(0.0, adur - vdur + 0.25)
print(f"video={vdur:.2f}s  vo(x{TEMPO})={adur:.2f}s  pad={pad:.2f}s")

# 2) 영상 끝프레임 홀드로 길이 맞추고, 원본 음소거 + VO
subprocess.run([FF, "-y", "-i", VID, "-i", vo_fast,
                "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.2f}[v]",
                "-map", "[v]", "-map", "1:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", OUT], check=True, capture_output=True)
print("FINAL:", OUT, os.path.getsize(OUT), "bytes")
print("final dur:", round(dur(OUT), 2), "s")
