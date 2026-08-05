#!/usr/bin/env python3
"""블로거 테마 CSS를 실제 라이브 페이지에 입혀 미리 본다.

    python3 tools/preview_theme.py --out preview_theme.html

왜 이렇게 하나:
- 블로거 테마 CSS는 붙여넣기 전에는 결과를 볼 수 없다. 감으로 쓰고 저장하고
  새로고침하는 왕복은 느리고, 잘못되면 라이브 블로그가 깨진 채로 남는다.
- Contempo 의 CSS 는 전부 페이지 안에 inline 이라 (외부 의존 없음)
  라이브 HTML 을 받아 오버라이드만 끼워 넣으면 브라우저가 보는 것과 같은 결과가 나온다.

미리보기 한계(아티팩트 CSP가 외부 요청을 막는다):
- 블로거 아이콘 스프라이트(/responsive/sprite_*.svg)는 안 뜬다 → 실물에서는 정상
- 웹폰트는 assets/fonts 의 서브셋을 data URI 로 인라인해 대체한다
"""
import argparse
import base64
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "blog", "theme", "contempo-override.css")
FONTS = os.path.join(ROOT, "assets", "fonts")


def font_face_block():
    """서브셋 woff2 를 data URI 로. unicode-range 를 주지 않아 이 폰트가 먼저 쓰인다."""
    out = []
    for weight, fn in ((400, "sub-Regular.woff2"), (600, "sub-SemiBold.woff2"), (700, "sub-Bold.woff2")):
        p = os.path.join(FONTS, fn)
        if not os.path.exists(p):
            continue
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        out.append(f"@font-face{{font-family:'Pretendard';font-style:normal;font-weight:{weight};"
                   f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    # 800(워드마크)은 Bold 로 대체 — 서브셋에 없는 굵기다
    out.append("@font-face{font-family:'Pretendard';font-style:normal;font-weight:800;"
               "font-display:swap;src:local('X')}")
    return "<style>" + "".join(out) + "</style>"


def strip_external(html):
    """아티팩트 CSP가 막을 요청을 미리 걷어낸다 — 콘솔 에러로 화면이 어수선해지지 않게."""
    html = re.sub(r'<link[^>]+href=[\'"][^\'"]*blogger\.com/dyn-css[^\'"]*[\'"][^>]*>', "", html)
    html = re.sub(r'<link[^>]+href=[\'"][^\'"]*cdn\.jsdelivr\.net[^\'"]*[\'"][^>]*>', "", html)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    html = re.sub(r"<script[^>]*/>", "", html)
    return html


def banner(label, note):
    return (f'<div style="position:sticky;top:0;z-index:9999;background:#12291f;color:#fff;'
            f'font:600 13px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;padding:9px 16px;'
            f'display:flex;gap:10px;align-items:baseline">'
            f'<span style="color:#b8791f">●</span><b>{label}</b>'
            f'<span style="opacity:.72;font-weight:400">{note}</span></div>')


def build(src, label, note, css, apply_css=True):
    html = strip_external(open(src, encoding="utf-8").read())
    inject = font_face_block() + (f"<style>{css}</style>" if apply_css else "")
    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + html
    m = re.search(r"<body[^>]*>", html)
    if m:
        html = html[:m.end()] + banner(label, note) + html[m.end():]
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None, help="라이브 HTML 을 받아둔 디렉터리")
    ap.add_argument("--out", required=True)
    ap.add_argument("--css", default=None, help="오버라이드 CSS 경로 (기본: 어디사)")
    ap.add_argument("--title", default="어디사", help="미리보기 제목")
    ap.add_argument("--page", action="append", default=[],
                    help="파일명:라벨:설명 (여러 번). 생략하면 어디사 기본값")
    args = ap.parse_args()

    src = args.src or os.path.dirname(os.path.abspath(args.out))
    css_path = args.css or CSS
    css_path = css_path if os.path.isabs(css_path) else os.path.join(ROOT, css_path)
    css = open(css_path, encoding="utf-8").read()
    # @import 는 아티팩트에서 어차피 차단되므로 인라인 서브셋으로 대체한다
    css = re.sub(r"@import[^;]+;", "", css)

    pages = [tuple(x.split(":", 2)) for x in args.page] or [
        ("home2.html", "홈 — 적용 후", "Contempo 기본 → 어디사"),
        ("live.html", "글 — 적용 후", "본문과 껍데기가 같은 팔레트"),
    ]
    parts = []
    for fn, label, note in pages:
        p = os.path.join(src, fn)
        if not os.path.exists(p):
            print(f"  건너뜀(없음): {fn}")
            continue
        out = os.path.join(src, "themed_" + fn)
        with open(out, "w", encoding="utf-8") as f:
            f.write(build(p, label, note, css))
        parts.append((label, out))
        print(f"  생성: {os.path.basename(out)} ({os.path.getsize(out):,}B)")

    # 두 페이지를 iframe 으로 나란히 — srcdoc 은 용량이 커서 blob 로 넣는다
    frames = ""
    for i, (label, path) in enumerate(parts):
        doc = open(path, encoding="utf-8").read()
        b64 = base64.b64encode(doc.encode()).decode()
        frames += (f'<section><h2>{label}</h2>'
                   f'<iframe id="f{i}" title="{label}"></iframe>'
                   f'<script type="application/octet-stream" id="d{i}">{b64}</script></section>')

    shell = f"""<title>{args.title} — 테마 미리보기</title>
<style>
 body{{margin:0;background:#eceaf2;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif}}
 .wrap{{max-width:1180px;margin:0 auto;padding:20px}}
 .lead{{background:#fff7ed;color:#9a3412;border:1px solid #fed7aa;border-radius:10px;
   padding:12px 15px;font-size:13.5px;line-height:1.65;margin:0 0 16px}}
 section{{margin:0 0 26px}}
 h2{{font-size:13px;letter-spacing:.06em;color:#3b3550;margin:0 0 8px}}
 iframe{{width:100%;height:82vh;border:1px solid #d8d4e4;border-radius:10px;background:#fff;
   box-shadow:0 6px 28px rgba(30,20,60,.10)}}
 @media (prefers-color-scheme:dark){{body{{background:#15131c}} h2{{color:#ded9ec}}}}
</style>
<div class="wrap">
<p class="lead"><b>실제 라이브 페이지</b>에 새 CSS를 입힌 결과입니다. 블로거 아이콘(햄버거·검색·공유)은
미리보기가 외부 요청을 막아 안 보이지만 <b>실물에서는 정상</b>입니다. 폰트도 서브셋이라 일부 글자가
기본 서체로 보일 수 있습니다.</p>
{frames}
</div>
<script>
document.querySelectorAll('iframe').forEach(function(f){{
  var d=document.getElementById('d'+f.id.slice(1));
  var html=new TextDecoder().decode(Uint8Array.from(atob(d.textContent),function(c){{return c.charCodeAt(0)}}));
  f.srcdoc=html;
}});
</script>"""
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(shell)
    print(f"\n미리보기: {args.out} · 페이지 {len(parts)}개")


if __name__ == "__main__":
    main()
