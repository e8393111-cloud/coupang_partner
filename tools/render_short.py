#!/usr/bin/env python3
"""숏폼 렌더러 (상품 무관, 설정 파일 기반).

products/<id>.json 하나만 바꾸면 새 상품 영상이 나온다.
- VO(mp3) 속도 조절(atempo) → 영상 길이에 맞춰 끝프레임 홀드(tpad)
- 상단 바: 원본 배너/워터마크 가림 + 공정위 문구 상시 노출
- 하단 바: 원본 자막 가림 + VO 싱크 새 자막
- 자막 타이밍은 JSON에 직접 적거나(--) silencedetect 자동 분할(--auto-caps)

사용법:
    python3 tools/render_short.py products/mosquito.json            # 렌더
    python3 tools/render_short.py products/mosquito.json --probe    # VO 무음 구간만 출력
    python3 tools/render_short.py products/mosquito.json --auto-caps # 무음 기준 자동 타이밍

drawtext가 없는 static ffmpeg를 쓰므로 자막은 PIL로 PNG를 그려 overlay 한다.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 한글 되는 시스템 폰트 (이모지는 안 나옴 → 자막에 이모지 쓰지 말 것)
DEFAULT_FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
DEFAULT_DISCLOSURE = "쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다"

DEFAULTS = {
    "width": 1080,
    "height": 1920,
    "vo_atempo": 1.5,
    "font": DEFAULT_FONT,
    "disclosure": DEFAULT_DISCLOSURE,
    "top_bar_h": 300,          # 상단 가림 바 높이(0이면 안 그림)
    "bottom_bar_y": 1060,      # 하단 가림 바 시작 y (화면 끝까지 채움)
    "caption_box_y1": 1740,    # 자막 세로 중앙 정렬용 하단 기준선
    "caption_size": 60,
    "disclosure_size": 36,
    "bar_color": [12, 14, 20],
    "tail_pad": 0.25,          # VO가 영상보다 길 때 끝프레임 홀드 여유(초)
}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe_duration(path):
    r = run([FF, "-i", path])
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        raise RuntimeError(f"duration 파싱 실패: {path}\n{r.stderr[-800:]}")
    h, mn, s = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(s)


def atempo_chain(rate):
    """atempo는 0.5~2.0만 받으므로 필요하면 여러 단으로 쪼갠다."""
    parts, r = [], float(rate)
    while r > 2.0:
        parts.append(2.0)
        r /= 2.0
    while r < 0.5:
        parts.append(0.5)
        r /= 0.5
    parts.append(round(r, 6))
    return ",".join(f"atempo={p}" for p in parts)


def speed_up_vo(src, dst, rate):
    r = run([FF, "-y", "-i", src, "-filter:a", atempo_chain(rate), "-c:a", "aac", "-b:a", "160k", dst])
    if r.returncode != 0:
        raise RuntimeError(f"VO 속도 변환 실패:\n{r.stderr[-800:]}")
    return dst


def detect_speech_spans(audio, noise_db=-25, min_silence=0.15):
    """무음 구간을 빼서 '말하는 구간' 리스트를 만든다 → 자막 타이밍 자동 매핑용."""
    r = run([FF, "-i", audio, "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    total = probe_duration(audio)
    spans, cur = [], 0.0
    for i, s in enumerate(starts):
        if s > cur + 0.05:
            spans.append((cur, s))
        cur = ends[i] if i < len(ends) else total
    if total > cur + 0.05:
        spans.append((cur, total))
    return spans, total


def auto_caption_times(spans, total, n):
    """말하는 구간 n개로 뭉쳐서 자막 n개에 배분. 구간이 부족하면 균등 분할."""
    if len(spans) < n:
        step = total / n
        return [(i * step, (i + 1) * step) for i in range(n)]
    # 인접 구간을 묶어 n덩어리로 (긴 구간이 경계가 되도록 뒤에서부터 붙임)
    groups, per = [], len(spans) / n
    for i in range(n):
        a = spans[int(round(i * per))][0]
        b = spans[int(round((i + 1) * per)) - 1][1]
        groups.append((a, b))
    # 자막이 끊기지 않게 다음 자막 시작까지 이어 붙임
    out = []
    for i, (a, b) in enumerate(groups):
        end = groups[i + 1][0] if i + 1 < len(groups) else total + 0.5
        out.append((a if i else 0.0, end))
    return out


def wrap_text(draw, text, font, maxw):
    if draw.textlength(text, font=font) <= maxw:
        return [text]
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_overlay_png(cfg, text, path):
    W, H = cfg["width"], cfg["height"]
    bar = tuple(cfg["bar_color"]) + (255,)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    top = cfg["top_bar_h"]
    if top > 0:
        d.rectangle([0, 0, W, top], fill=bar)
        dfont = ImageFont.truetype(cfg["font"], cfg["disclosure_size"])
        dlines = wrap_text(d, cfg["disclosure"], dfont, W - 70)
        dlh = int(cfg["disclosure_size"] * 1.28)
        dy = (top - dlh * len(dlines)) // 2
        for i, ln in enumerate(dlines):
            tw = d.textlength(ln, font=dfont)
            d.text(((W - tw) / 2, dy + i * dlh), ln, font=dfont, fill=(205, 208, 215, 255))

    y0 = cfg["bottom_bar_y"]
    d.rectangle([0, y0, W, H], fill=bar)
    font = ImageFont.truetype(cfg["font"], cfg["caption_size"])
    lines = wrap_text(d, text, font, W - 120)
    lh = int(cfg["caption_size"] * 1.27)
    cy = (y0 + cfg["caption_box_y1"]) // 2 - (lh * len(lines)) // 2
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        d.text(((W - tw) / 2, cy + i * lh), ln, font=font, fill=(255, 255, 255, 255),
               stroke_width=3, stroke_fill=(0, 0, 0, 255))
    img.save(path)


def load_config(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    cfg = dict(DEFAULTS)
    cfg.update(raw)
    for key in ("video", "vo", "out"):
        if key not in cfg:
            raise SystemExit(f"설정에 '{key}' 가 없습니다: {path}")
        cfg[key] = cfg[key] if os.path.isabs(cfg[key]) else os.path.join(ROOT, cfg[key])
    if not os.path.exists(cfg["font"]):
        raise SystemExit(f"폰트 없음: {cfg['font']}")
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="products/<id>.json")
    ap.add_argument("--probe", action="store_true", help="VO 말하는 구간만 출력하고 종료")
    ap.add_argument("--auto-caps", action="store_true", help="자막 타이밍을 무음 기준으로 자동 배분")
    args = ap.parse_args()

    cfg = load_config(args.config)
    caps = cfg.get("captions") or []
    if not caps:
        raise SystemExit("captions 가 비어 있습니다")

    tmp = tempfile.mkdtemp(prefix="short_")
    vo_fast = speed_up_vo(cfg["vo"], os.path.join(tmp, "vo_fast.m4a"), cfg["vo_atempo"])
    spans, adur = detect_speech_spans(vo_fast)

    if args.probe:
        print(f"VO({cfg['vo_atempo']}x) 길이 {adur:.2f}s · 말하는 구간 {len(spans)}개")
        for i, (a, b) in enumerate(spans):
            print(f"  {i}: {a:6.2f} → {b:6.2f}  ({b - a:.2f}s)")
        return

    if args.auto_caps or any("start" not in c for c in caps):
        times = auto_caption_times(spans, adur, len(caps))
        for c, (a, b) in zip(caps, times):
            c["start"], c["end"] = round(a, 2), round(b, 2)
        print("자동 자막 타이밍:", [(c["start"], c["end"]) for c in caps])

    vdur = probe_duration(cfg["video"])
    pad = max(0.0, adur - vdur + cfg["tail_pad"])

    inputs = ["-i", cfg["video"], "-i", vo_fast]
    for i, c in enumerate(caps):
        png = os.path.join(tmp, f"cap{i}.png")
        make_overlay_png(cfg, c["text"], png)
        inputs += ["-i", png]

    fc = [f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.2f}[v0]"]
    prev = "v0"
    for i, c in enumerate(caps):
        end = c.get("end") or adur + 0.5
        nxt = f"v{i + 1}"
        fc.append(f"[{prev}][{i + 2}:v]overlay=0:0:enable='between(t,{c['start']:.2f},{end:.2f})'[{nxt}]")
        prev = nxt

    os.makedirs(os.path.dirname(cfg["out"]), exist_ok=True)
    r = run([FF, "-y", *inputs, "-filter_complex", ";".join(fc),
             "-map", f"[{prev}]", "-map", "1:a",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", cfg["out"]])
    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        raise SystemExit("렌더 실패")

    print(f"영상 {vdur:.2f}s · VO {adur:.2f}s · 홀드 {pad:.2f}s")
    print(f"완성: {cfg['out']} ({os.path.getsize(cfg['out']):,} bytes, {probe_duration(cfg['out']):.2f}s)")


if __name__ == "__main__":
    main()
