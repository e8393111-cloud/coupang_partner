#!/usr/bin/env python3
"""상품 상세페이지(랜딩) 생성기.

products/<id>.json 의 "landing" 블록 + tools/landing_template.html → p/<id>.html

사용법:
    python3 tools/make_landing.py products/mosquito.json
    python3 tools/make_landing.py products/mosquito.json --deeplink "https://link.coupang.com/a/XXXX"

--deeplink 를 주면 JSON에도 저장되므로, 딥링크는 한 번만 넣으면 된다.
"""
import argparse
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "tools", "landing_template.html")
PLACEHOLDER = "COUPANG_DEEPLINK"


def esc(s):
    return html.escape(str(s), quote=True)


def render_pains(items):
    return "\n".join(f"      <li>{esc(t)}</li>" for t in items)


def render_steps(items):
    out = []
    for i, s in enumerate(items, 1):
        out.append(
            f'      <div class="step"><div class="n">{i}</div>'
            f'<div><h3>{esc(s["h"])}</h3><p>{esc(s["p"])}</p></div></div>'
        )
    return "\n".join(out)


def render_uses(items):
    out = []
    for u in items:
        fb = u.get("fallback", "")
        fb_attr = f' data-fallback="{esc(fb)}"' if fb else ""
        out.append(
            f'      <div class="uc"><img src="{esc(u["img"])}"{fb_attr} alt="{esc(u.get("alt", ""))}" loading="lazy">'
            f'<div class="lb">{esc(u["label"])}</div></div>'
        )
    return "\n".join(out)


def render_facts(items):
    return "\n".join(
        f'      <div class="fact"><div class="big">{esc(f["big"])}</div>'
        f'<div class="sm">{esc(f["sm"])}</div></div>'
        for f in items
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--deeplink", help="쿠파스 딥링크. 주면 JSON에도 저장된다")
    args = ap.parse_args()

    cfg_path = args.config if os.path.isabs(args.config) else os.path.join(ROOT, args.config)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    L = cfg["landing"]

    if args.deeplink:
        L["deeplink"] = args.deeplink
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")

    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()

    # h1/sub 는 <br> 를 쓰므로 이스케이프하지 않는 raw 필드
    raw_fields = {"h1", "sub"}
    tokens = {
        "title": esc(L["title"]),
        "og_title": esc(L.get("og_title", L["title"])),
        "og_desc": esc(L["og_desc"]),
        "eyebrow": esc(L["eyebrow"]),
        "h1": L["h1"],
        "sub": L["sub"],
        "video_src": esc(L["video_src"]),
        "price": esc(L["price"]),
        "list_price": esc(L["list_price"]),
        "price_note": esc(L["price_note"]),
        "pain_title": esc(L["pain_title"]),
        "pains": render_pains(L["pains"]),
        "how_title": esc(L["how_title"]),
        "steps": render_steps(L["steps"]),
        "use_title": esc(L["use_title"]),
        "uses": render_uses(L["uses"]),
        "spec_title": esc(L["spec_title"]),
        "facts": render_facts(L["facts"]),
        "cta": esc(L["cta"]),
        "cta_sub": esc(L["cta_sub"]),
        "sticky_cta": esc(L["sticky_cta"]),
        "deeplink": esc(L.get("deeplink", PLACEHOLDER)),
    }
    assert raw_fields <= set(tokens)

    out_html = tpl
    for k, v in tokens.items():
        out_html = out_html.replace("{{%s}}" % k, v)
    left = [t for t in ("{{",) if t in out_html]
    if left:
        raise SystemExit("치환 안 된 토큰이 남았습니다: " + out_html.split("{{", 1)[1][:40])

    out_path = os.path.join(ROOT, L["out"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)

    print("생성:", out_path)
    if L.get("deeplink", PLACEHOLDER) == PLACEHOLDER:
        print("⚠️  딥링크 미설정 — 구매 버튼은 비활성 상태입니다.")
        print("    쿠파스 딥링크 받으면: python3 tools/make_landing.py %s --deeplink \"<링크>\"" % args.config)


if __name__ == "__main__":
    main()
