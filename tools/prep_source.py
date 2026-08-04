#!/usr/bin/env python3
"""소스 영상 정리 — 배너/워터마크 크롭 + 필요한 구간만 트림 + 이어붙이기.

Mirra 초벌이든 소싱한 raw 제품 클립이든, 렌더 전에 여기서 깨끗한 9:16 소스를 만든다.
products/<id>.json 의 "prep" 블록을 읽는다:

    "prep": {
      "src": "footage/mirra_raw.mp4",   또는 ["a.mp4", "b.mp4"] (클립 여러 개 이어붙이기)
      "crop": "1001:1780:39:140",       (w:h:x:y — 배너/워터마크 잘라내기, 없으면 생략)
      "segments": [[0.0, 3.0], [22.0, 12.0]],   (시작초, 길이초) — 없으면 통째로
      "out": "assets/mirra_cleaned.mp4"
    }

src가 리스트면 segments[i] 가 src[i] 에 대응한다(길이가 같아야 함).

사용법:
    python3 tools/prep_source.py products/mosquito.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_duration(path):
    r = run([FF, "-i", path])
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        raise RuntimeError(f"duration 파싱 실패: {path}")
    h, mn, s = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(s)


def abspath(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def build_vf(prep, crop=None):
    """crop 은 구간별로 다를 수 있다.

    렌더러가 상·하단에 불투명 바를 그리므로, 피사체가 낮게 잡힌 컷은
    아래를 잘라 위로 올려야 바에 안 잘린다. 재생성보다 훨씬 싸다.
    """
    parts = []
    c = crop if crop is not None else prep.get("crop")
    if c:
        parts.append(f"crop={c}")
    w, h = prep.get("width", 1080), prep.get("height", 1920)
    parts.append(f"scale={w}:{h}")
    parts.append("setsar=1")
    return ",".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    args = ap.parse_args()

    cfg_path = abspath(args.config)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    prep = cfg.get("prep")
    if not prep:
        raise SystemExit(f"{args.config} 에 'prep' 블록이 없습니다")

    srcs = prep["src"] if isinstance(prep["src"], list) else [prep["src"]]
    srcs = [abspath(s) for s in srcs]
    for s in srcs:
        if not os.path.exists(s):
            raise SystemExit(f"소스 없음: {s}\n(사용자가 repo 에 업로드하고 git pull 했는지 확인)")

    segs = prep.get("segments")
    if not segs:
        segs = [[0.0, round(probe_duration(s), 2)] for s in srcs]
    if len(srcs) > 1 and len(segs) != len(srcs):
        raise SystemExit("src 가 여러 개면 segments 개수도 같아야 합니다")

    # crops[i] 가 있으면 그 구간만 다른 crop 을 쓴다. 없으면 prep.crop(전역).
    crops = prep.get("crops")
    if crops and len(crops) != len(segs):
        raise SystemExit("crops 를 쓰려면 segments 와 개수가 같아야 합니다")

    fps = prep.get("fps", 30)
    tmp = tempfile.mkdtemp(prefix="prep_")
    parts = []
    for i, (ss, dur) in enumerate(segs):
        src = srcs[i] if len(srcs) > 1 else srcs[0]
        vf = build_vf(prep, crops[i] if crops else None)
        out = os.path.join(tmp, f"p{i}.mp4")
        r = run([FF, "-y", "-ss", str(ss), "-t", str(dur), "-i", src,
                 "-vf", vf, "-r", str(fps),
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", out])
        if r.returncode != 0:
            print(r.stderr[-1500:], file=sys.stderr)
            raise SystemExit(f"구간 {i} 트림 실패")
        parts.append(out)
        print(f"  컷 {i}: {os.path.basename(src)} {ss}s +{dur}s → {probe_duration(out):.2f}s")

    out_path = abspath(prep["out"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if len(parts) == 1:
        os.replace(parts[0], out_path)
    else:
        listf = os.path.join(tmp, "list.txt")
        with open(listf, "w") as f:
            f.write("".join(f"file '{p}'\n" for p in parts))
        r = run([FF, "-y", "-f", "concat", "-safe", "0", "-i", listf, "-c", "copy", out_path])
        if r.returncode != 0:
            print(r.stderr[-1500:], file=sys.stderr)
            raise SystemExit("이어붙이기 실패")

    print(f"정리 완료: {out_path} ({os.path.getsize(out_path):,} bytes, {probe_duration(out_path):.2f}s)")
    print("다음: python3 tools/render_short.py %s" % args.config)


if __name__ == "__main__":
    main()
