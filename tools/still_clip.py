#!/usr/bin/env python3
"""정지 이미지 → 슬로우 줌 클립 (Ken Burns). 생성 크레딧 0.

    python3 tools/still_clip.py IMG OUT [--dur 1.5] [--zoom 1.08] [--out-w 1080] [--out-h 1920] [--fps 30]

왜: 잔량 창·계량컵·밤 거실처럼 피사체가 정지인 1초 안팎 비트는
영상 생성(8.75크레딧)이 낭비다. 느린 줌만 있어도 컷으로 성립한다.

zoompan 은 프레임 단위로 확대율을 올린다. 시작 1.0 → 끝 --zoom.
출력은 prep_source.py 규격과 동일(1080x1920/30fps/libx264/yuv420p)이라
바로 src 목록에 넣을 수 있다. 오디오 트랙은 없다 — 어차피 렌더러가 버린다.
"""
import argparse
import os
import subprocess

import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = imageio_ffmpeg.get_ffmpeg_exe()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("img")
    ap.add_argument("out")
    ap.add_argument("--dur", type=float, default=1.5)
    ap.add_argument("--zoom", type=float, default=1.08)
    ap.add_argument("--out-w", type=int, default=1080)
    ap.add_argument("--out-h", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()

    img = a.img if os.path.isabs(a.img) else os.path.join(ROOT, a.img)
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    frames = max(2, round(a.dur * a.fps))

    # 고해상 원본을 먼저 2배로 키워 줌 계단현상(지터)을 줄인 뒤 zoompan.
    vf = (f"scale={a.out_w * 2}:{a.out_h * 2}:force_original_aspect_ratio=increase,"
          f"crop={a.out_w * 2}:{a.out_h * 2},"
          f"zoompan=z='1+({a.zoom}-1)*on/{frames - 1}'"
          f":d={frames}:s={a.out_w}x{a.out_h}:fps={a.fps},"
          f"setsar=1")
    r = subprocess.run(
        [FF, "-y", "-loop", "1", "-i", img, "-vf", vf,
         "-frames:v", str(frames),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", out],
        capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-800:])
    print(f"{os.path.relpath(out, ROOT)} · {a.dur}s · zoom {a.zoom} · {os.path.getsize(out):,}B")


if __name__ == "__main__":
    main()
