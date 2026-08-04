#!/usr/bin/env python3
"""스토리보드 장부 — 컷 이미지·클립 생성을 관리한다.

    python3 tools/make_shots.py lint    products/pawsie.shots.json
    python3 tools/make_shots.py payload products/pawsie.shots.json --stage image --preflight
    python3 tools/make_shots.py cost    products/pawsie.shots.json --id s1 --credits 3
    python3 tools/make_shots.py gate    products/pawsie.shots.json
    python3 tools/make_shots.py payload products/pawsie.shots.json --stage image --submit
    python3 tools/make_shots.py record  products/pawsie.shots.json --id s1 --job JOB --url URL --credits 3
    python3 tools/make_shots.py fetch   products/pawsie.shots.json
    python3 tools/make_shots.py sheet   products/pawsie.shots.json
    python3 tools/make_shots.py approve products/pawsie.shots.json s1
    python3 tools/make_shots.py reject  products/pawsie.shots.json s3 --note "손이 나옴"
    python3 tools/make_shots.py emit    products/pawsie.shots.json

**이 스크립트는 higgsfield 를 호출하지 않는다.** repo 가 공개라 API 키를 둘 수 없고
higgsfield 는 MCP 로만 닿는다. 그래서 역할을 나눈다:

    스크립트  설정 검증 · 페이로드 조립 · 지출 장부 · 다운로드 · 대지 · prep 산출
    에이전트  MCP 호출 (media_import_url / generate_image / generate_video)

`payload --submit` 은 모든 항목에 est_cost 가 기록되고 gate 가 통과해야만 출력한다.
예산을 넘기면 페이로드 자체를 얻을 수 없다 — 이게 하드 스톱이다.

설계 근거는 PLAN 「스토리보드 → 속도감 있는 페이스리스 숏폼」.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOBAL_TRUTH = os.path.join(ROOT, "products", "_truth_global.json")


# ───────────────────────── 공통 ─────────────────────────

def rp(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load(path):
    with open(rp(path), encoding="utf-8") as f:
        return json.load(f)


def save(path, cfg):
    with open(rp(path), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def merged_truth(cfg):
    """전역 규칙 + 제품 규칙. 전역이 먼저 오고 제품이 덧붙는다(덮어쓰지 않는다)."""
    g = load(GLOBAL_TRUTH) if os.path.exists(GLOBAL_TRUTH) else {}
    t = cfg.get("truth") or {}
    return {
        "never_show": (g.get("never_show") or []) + (t.get("never_show") or []),
        "may_show": t.get("may_show") or {},
        "review_evidence": t.get("review_evidence") or [],
        "require": g.get("require") or {},
        "prompt_suffix": (cfg.get("defaults") or {}).get("prompt_suffix")
                         or g.get("prompt_suffix") or "",
    }


def items(cfg, stage):
    return cfg.get("shots" if stage == "image" else "clips") or []


def find(cfg, iid):
    for stage in ("image", "video"):
        for it in items(cfg, stage):
            if it.get("id") == iid:
                return it, stage
    raise SystemExit(f"없는 id: {iid}")


def full_prompt(it, truth):
    return f'{it["prompt"].strip()}. {truth["prompt_suffix"]}'.strip()


# ───────────────────────── lint ─────────────────────────

def cmd_lint(cfg, args, path):
    truth = merged_truth(cfg)
    errs, warns = [], []

    # ① 금지 표현
    for stage in ("image", "video"):
        for it in items(cfg, stage):
            p = it.get("prompt") or ""
            for rule in truth["never_show"]:
                if re.search(rule["pattern"], p):
                    errs.append(f'{it["id"]}: 금지 표현 — {rule["why"]}\n      "{p[:70]}"')

    # ② 주장 허용목록 — 등록되지 않은 건 금지
    for it in items(cfg, "image"):
        claims = it.get("truth_claims")
        if not claims:
            errs.append(f'{it["id"]}: truth_claims 가 비었다. 무엇을 보여주는지 선언해야 한다')
            continue
        for c in claims:
            if c not in truth["may_show"]:
                errs.append(f'{it["id"]}: 미등록 주장 "{c}" — truth.may_show 에 없다')
            elif not any(e.get("claim") == c for e in truth["review_evidence"]):
                warns.append(f'{it["id"]}: 주장 "{c}" 에 후기 근거가 없다 (승인 시 --force 필요)')

    # ③ 클립은 무음이어야 concat 이 깨지지 않는다
    req = truth["require"]
    if req.get("video_sound") == "off":
        for it in items(cfg, "video"):
            prm = it.get("params") or (cfg.get("defaults") or {}).get("video_params") or {}
            if prm.get("sound") not in ("off", None) or prm.get("generate_audio") is True:
                errs.append(f'{it["id"]}: 오디오가 켜져 있다. concat 이 깨지고 돈도 더 든다')

    # ④ 속도감 — 첫 hook_sec 안에 컷이 2개 이상이어야 훅이다
    pace = cfg.get("pace") or {}
    cuts = cfg.get("cuts") or []
    if cuts:
        hook_sec = pace.get("hook_sec", 3.0)
        lo, hi = pace.get("beat_range", [0.6, 1.8])
        t, n_hook = 0.0, 0
        for c in cuts:
            if t < hook_sec:
                n_hook += 1
            if not (lo <= c["dur"] <= hi):
                errs.append(f'컷 {c["clip"]}@{c["start"]}: 길이 {c["dur"]}s 가 '
                            f'beat_range [{lo}, {hi}] 밖이다')
            t += c["dur"]
        if n_hook < 2:
            errs.append(f"첫 {hook_sec}초에 컷이 {n_hook}개뿐이다. 훅은 시퀀스여야 한다 (2개 이상)")
        print(f"  총 길이 {t:.2f}s · 컷 {len(cuts)}개 · 평균 {t/len(cuts):.2f}s · 훅 구간 {n_hook}컷")

    # ⑤ 훅 자막 길이
    first = (cfg.get("hook_caption") or "").strip()
    if first and len(first) > 12:
        errs.append(f'훅 자막이 {len(first)}자다. 12자 이내여야 1.2초에 읽힌다: "{first}"')

    for w in warns:
        print(f"  ⚠ {w}")
    if errs:
        print(f"\n✗ {len(errs)}건")
        for e in errs:
            print(f"  · {e}")
        sys.exit(1)
    print(f"✓ lint 통과 (경고 {len(warns)}건)")


# ──────────────────────── payload ────────────────────────

def cmd_payload(cfg, args, path):
    truth = merged_truth(cfg)
    d = cfg.get("defaults") or {}
    stage = args.stage
    pend = [i for i in items(cfg, stage)
            if i.get("state") in (None, "planned", "cost_known", "rejected")]
    if args.id:
        pend = [i for i in pend if i["id"] == args.id]
    if not pend:
        raise SystemExit("생성할 항목이 없다")

    if args.submit:
        cmd_lint(cfg, args, path)
        missing = [i["id"] for i in pend if i.get("est_cost") is None]
        if missing:
            raise SystemExit(f"est_cost 미기록: {', '.join(missing)} → 먼저 --preflight 후 cost 로 기록")
        check_gate(cfg, pend, hard=True)

    out = []
    for it in pend:
        if stage == "image":
            p = {"model": it.get("model") or d.get("image_model"),
                 "prompt": full_prompt(it, truth),
                 "aspect_ratio": d.get("aspect_ratio", "9:16"),
                 "count": it.get("count", 1)}
            refs = [r for r in (cfg.get("refs") or []) if r["key"] in (it.get("refs") or [])]
            miss = [r["key"] for r in refs if not r.get("media_id")]
            if miss:
                raise SystemExit(f'{it["id"]}: media_id 없음 {miss} → media_import_url 먼저')
            if refs:
                p["medias"] = [{"value": r["media_id"], "role": "image_references"} for r in refs]
        else:
            src = it.get("from")
            sh, _ = find(cfg, src)
            if not sh.get("chosen"):
                raise SystemExit(f'{it["id"]}: 시작 컷 {src} 이 아직 승인되지 않았다')
            p = {"model": it.get("model") or d.get("video_model"),
                 "prompt": full_prompt(it, truth),
                 "aspect_ratio": d.get("aspect_ratio", "9:16"),
                 **(d.get("video_params") or {}), **(it.get("params") or {}),
                 "medias": [{"value": sh["chosen"]["job_id"], "role": "start_image"}]}
        if args.preflight:
            p["get_cost"] = True
            p.pop("count", None)
        out.append({"id": it["id"], "params": p})

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.preflight:
        print("\n# get_cost=true — 잡을 제출하지 않는다. 결과는 cost 로 기록할 것.", file=sys.stderr)


# ───────────────────── cost / gate ─────────────────────

def check_gate(cfg, pend, hard=False):
    b = cfg.get("budget") or {}
    cap, reserve = b.get("cap_credits", 0), b.get("reserve_credits", 0)
    spent = b.get("spent", 0)
    bal = b.get("balance")
    est = sum(i.get("est_cost") or 0 for i in pend)

    print(f"  예상 {est:.2f} · 누적 {spent:.2f} · 상한 {cap}")
    bad = []
    if spent + est > cap:
        bad.append(f"상한 초과: {spent:.2f}+{est:.2f}={spent+est:.2f} > {cap}")
    if bal is not None and bal - est < reserve:
        bad.append(f"예비분 침범: 잔액 {bal:.2f}-{est:.2f}={bal-est:.2f} < {reserve}")
    if bad:
        for x in bad:
            print(f"  ✗ {x}")
        if hard:
            sys.exit(1)
        return False
    print("  ✓ 예산 통과")
    return True


def cmd_cost(cfg, args, path):
    it, _ = find(cfg, args.id)
    it["est_cost"] = args.credits
    if it.get("state") in (None, "planned"):
        it["state"] = "cost_known"
    save(path, cfg)
    print(f'{args.id}: est_cost = {args.credits}')


def cmd_gate(cfg, args, path):
    if args.balance is not None:
        cfg.setdefault("budget", {})["balance"] = args.balance
        save(path, cfg)
    pend = [i for stage in ("image", "video") for i in items(cfg, stage)
            if i.get("state") in ("cost_known", "planned")]
    sys.exit(0 if check_gate(cfg, pend) else 1)


# ──────────────────── record / fetch ────────────────────

def cmd_record(cfg, args, path):
    it, stage = find(cfg, args.id)
    att = it.setdefault("attempts", [])
    att.append({"n": len(att) + 1, "job_id": args.job, "url": args.url,
                "credits": args.credits, "state": "pending_review",
                "local": None, "w": None, "h": None, "ts": now()})
    it["state"] = "pending_review"
    b = cfg.setdefault("budget", {})
    b["spent"] = round(b.get("spent", 0) + (args.credits or 0), 2)
    if args.balance is not None:
        b["balance"] = args.balance
    cfg.setdefault("log", []).append(
        {"ts": now(), "id": args.id, "act": "record", "credits": args.credits})
    save(path, cfg)
    print(f'{args.id}: 시도 {len(att)} 기록 · 누적 지출 {b["spent"]}')


def probe(p):
    """이미지든 영상이든 크기를 잰다. prep_source.py 가 9:16 이 아니면 소리 없이 찌그러뜨린다."""
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None, None
    r = subprocess.run([ff, "-i", p], capture_output=True, text=True)
    m = re.search(r"(\d{2,5})x(\d{2,5})", r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def cmd_fetch(cfg, args, path):
    """cloudfront URL 은 만료된다 → 생성 직후 받아서 repo 에 남긴다 (HANDOFF §3)."""
    out_dir = rp(cfg.get("out_dir") or "assets/shots")
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for stage in ("image", "video"):
        for it in items(cfg, stage):
            for a in it.get("attempts") or []:
                if a.get("local") and os.path.exists(rp(a["local"])):
                    continue
                if not a.get("url"):
                    continue
                ext = ".mp4" if stage == "video" else os.path.splitext(a["url"].split("?")[0])[1] or ".png"
                loc = os.path.join(out_dir, f'{cfg["id"]}_{it["id"]}_v{a["n"]}{ext}')
                r = subprocess.run(["curl", "-sSL", "--max-time", "120", "-o", loc, a["url"]],
                                   capture_output=True, text=True)
                if r.returncode or not os.path.exists(loc) or os.path.getsize(loc) < 1024:
                    print(f'  ✗ {it["id"]} v{a["n"]} 실패 (URL 만료 가능)')
                    continue
                a["local"] = os.path.relpath(loc, ROOT)
                a["w"], a["h"] = probe(loc)
                n += 1
                print(f'  ✓ {a["local"]}  {a["w"]}x{a["h"]}  {os.path.getsize(loc):,}B')
    save(path, cfg)
    print(f"{n}건 받음")


# ──────────────────── approve / reject ────────────────────

def cmd_approve(cfg, args, path):
    it, _ = find(cfg, args.id)
    truth = merged_truth(cfg)
    unverified = [c for c in (it.get("truth_claims") or [])
                  if not any(e.get("claim") == c for e in truth["review_evidence"])]
    if unverified and not args.force:
        raise SystemExit(f'{args.id}: 근거 없는 주장 {unverified} → --force --reason "..." 필요')
    atts = it.get("attempts") or []
    if not atts:
        raise SystemExit(f"{args.id}: 시도가 없다")
    a = atts[args.attempt - 1] if args.attempt else atts[-1]
    a["state"] = "approved"
    it["chosen"] = {"job_id": a["job_id"], "local": a.get("local"), "n": a["n"]}
    it["state"] = "approved"
    cfg.setdefault("log", []).append({"ts": now(), "id": args.id, "act": "approve",
                                      "forced": bool(args.force), "reason": args.reason})
    save(path, cfg)
    print(f'{args.id}: 시도 {a["n"]} 승인' + (" (강제)" if args.force else ""))


def cmd_reject(cfg, args, path):
    it, _ = find(cfg, args.id)
    atts = it.get("attempts") or []
    if not atts:
        raise SystemExit(f"{args.id}: 시도가 없다")
    a = atts[args.attempt - 1] if args.attempt else atts[-1]
    a["state"] = "rejected"
    a["note"] = args.note
    it["state"] = "rejected"
    cfg.setdefault("log", []).append({"ts": now(), "id": args.id, "act": "reject", "note": args.note})
    save(path, cfg)
    print(f'{args.id}: 시도 {a["n"]} 반려 — {args.note}')
    print("  (시도 기록은 남긴다. 다음 세션이 같은 프롬프트를 다시 태우지 않도록)")


# ───────────────────────── sheet ─────────────────────────

def cmd_sheet(cfg, args, path):
    """대지 1장. 사용자가 URL 하나만 보고 한 번에 판정하게."""
    from PIL import Image, ImageDraw, ImageFont
    FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
    truth = merged_truth(cfg)
    cells = []
    for it in items(cfg, "image"):
        for a in it.get("attempts") or []:
            if a.get("local") and os.path.exists(rp(a["local"])):
                cells.append((it, a))
    if not cells:
        raise SystemExit("받아둔 이미지가 없다 — fetch 먼저")

    TW, TH, PAD, CAP = 300, 533, 14, 92
    cols = min(4, len(cells))
    rows = (len(cells) + cols - 1) // cols
    W = cols * (TW + PAD) + PAD
    H = rows * (TH + CAP + PAD) + PAD + 46
    sheet = Image.new("RGB", (W, H), (18, 41, 31))
    d = ImageDraw.Draw(sheet)
    f_t = ImageFont.truetype(FONT, 22)
    f_s = ImageFont.truetype(FONT, 15)
    f_x = ImageFont.truetype(FONT, 13)
    d.text((PAD, 12), f'{cfg["id"]} — 컷 검토  ({len(cells)}장)', font=f_t, fill=(255, 255, 255))

    for i, (it, a) in enumerate(cells):
        x = PAD + (i % cols) * (TW + PAD)
        y = 46 + (i // cols) * (TH + CAP + PAD)
        try:
            im = Image.open(rp(a["local"])).convert("RGB")
            im.thumbnail((TW, TH))
            sheet.paste(im, (x + (TW - im.width) // 2, y))
        except Exception as e:
            d.rectangle([x, y, x + TW, y + TH], outline=(200, 80, 80))
            d.text((x + 8, y + 8), f"열기 실패\n{e}", font=f_x, fill=(220, 120, 120))
        st = (a.get("state") or "pending")
        col = {"approved": (120, 220, 160), "rejected": (230, 120, 120)}.get(st, (230, 230, 230))
        d.text((x, y + TH + 4), f'{it["id"]} v{a["n"]}  [{st}]', font=f_s, fill=col)
        ty = y + TH + 24
        for c in (it.get("truth_claims") or []):
            ok = any(e.get("claim") == c for e in truth["review_evidence"])
            d.text((x, ty), ("✓ " if ok else "⚠ UNVERIFIED ") + c[:24], font=f_x,
                   fill=(150, 210, 180) if ok else (220, 170, 90))
            ty += 17
        if a.get("w"):
            ar = a["w"] / a["h"]
            bad = abs(ar - 9 / 16) > 0.01
            d.text((x, ty), f'{a["w"]}x{a["h"]}' + ("  ✗ 9:16 아님" if bad else ""),
                   font=f_x, fill=(220, 120, 120) if bad else (130, 150, 140))

    out = rp(args.out or f'assets/shots/{cfg["id"]}_sheet.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print(f"대지: {os.path.relpath(out, ROOT)}  ({W}x{H})")


# ───────────────────────── emit ─────────────────────────

def cmd_emit(cfg, args, path):
    """cuts → prep 블록. 같은 클립이 src 에 여러 번 들어간다(공짜 재단)."""
    cuts = cfg.get("cuts") or []
    if not cuts:
        raise SystemExit("cuts 가 비었다")
    src, seg = [], []
    for c in cuts:
        # zoompan(still_clip.py)으로 만든 컷은 생성 장부에 없다 — 경로를 그대로 쓴다.
        if c.get("direct"):
            if not os.path.exists(rp(c["direct"])):
                raise SystemExit(f'{c["direct"]}: 파일이 없다')
            src.append(c["direct"])
            seg.append([c["start"], c["dur"]])
            continue
        it, _ = find(cfg, c["clip"])
        ch = it.get("chosen")
        if not ch or not ch.get("local"):
            raise SystemExit(f'{c["clip"]}: 승인된 로컬 파일이 없다')
        a = next((x for x in it["attempts"] if x["n"] == ch["n"]), None)
        if a and a.get("w"):
            ar = a["w"] / a["h"]
            if abs(ar - 9 / 16) > 0.01:
                raise SystemExit(f'{c["clip"]}: {a["w"]}x{a["h"]} 는 9:16 이 아니다. '
                                 f'prep_source.py 가 소리 없이 찌그러뜨린다')
        src.append(ch["local"])
        seg.append([c["start"], c["dur"]])

    total = sum(s[1] for s in seg)
    prep = {"_주석": f"make_shots.py emit 생성 — 컷 {len(seg)}개 · 총 {total:.2f}s",
            "src": src, "crop": "", "fps": 30,
            "segments": seg, "out": f'assets/{cfg["id"]}_cut.mp4'}

    tgt = rp(cfg["product_ref"])
    p = load(tgt)
    p["prep"] = prep
    p["video"] = prep["out"]
    save(tgt, p)
    print(f'{cfg["product_ref"]} 의 prep 갱신 — 컷 {len(seg)}개 · {total:.2f}s '
          f'· 평균 {total/len(seg):.2f}s')
    print(f'다음: python3 tools/prep_source.py {cfg["product_ref"]}')


# ───────────────────────── main ─────────────────────────

CMDS = {"lint": cmd_lint, "payload": cmd_payload, "cost": cmd_cost, "gate": cmd_gate,
        "record": cmd_record, "fetch": cmd_fetch, "sheet": cmd_sheet,
        "approve": cmd_approve, "reject": cmd_reject, "emit": cmd_emit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=CMDS)
    ap.add_argument("data")
    ap.add_argument("id", nargs="?", help="대상 id (또는 --id)")
    ap.add_argument("--id", dest="id_opt", help="위치 인자 대신 쓸 수 있다")
    ap.add_argument("--stage", choices=["image", "video"], default="image")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--credits", type=float)
    ap.add_argument("--balance", type=float)
    ap.add_argument("--job")
    ap.add_argument("--url")
    ap.add_argument("--note")
    ap.add_argument("--reason")
    ap.add_argument("--attempt", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    args.id = args.id or args.id_opt
    if args.cmd in ("cost", "record", "approve", "reject") and not args.id:
        raise SystemExit(f"{args.cmd} 에는 id 가 필요하다 (위치 인자 또는 --id)")
    CMDS[args.cmd](load(args.data), args, args.data)


if __name__ == "__main__":
    main()
