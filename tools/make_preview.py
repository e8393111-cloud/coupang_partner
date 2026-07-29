#!/usr/bin/env python3
"""생성된 글을 "블로거에 올라간 모습"으로 감싸 미리보기 파일을 만든다.

글 자체 CSS 는 건드리지 않는다. 미리보기 틀(상단 바·안내문·흰 카드)만 씌운다.
블로거는 흰 배경에 렌더되므로 본문 영역은 뷰어 테마와 무관하게 라이트로 고정한다 —
그래야 실제 발행 화면과 같게 보인다.

사용법:
    python3 tools/make_preview.py posts_data/feeder.json
"""
import argparse
import base64
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHELL = """<title>어디사 — 글 미리보기</title>
<style>
  :root{
    --chrome-bg:#eceaf2; --chrome-fg:#3b3550; --chrome-mut:#6f6885;
    --chrome-line:#d8d4e4; --accent:#7c3aed;
    --note-bg:#fff7ed; --note-fg:#9a3412; --note-line:#fed7aa;
    --ok-bg:#ecfdf5; --ok-fg:#065f46; --ok-line:#a7f3d0;
  }
  @media (prefers-color-scheme:dark){ :root{
    --chrome-bg:#15131c; --chrome-fg:#ded9ec; --chrome-mut:#9a92b0;
    --chrome-line:#2a2637; --accent:#a78bfa;
    --note-bg:#2a1c12; --note-fg:#fdba74; --note-line:#4a2f1a;
    --ok-bg:#0f2620; --ok-fg:#6ee7b7; --ok-line:#1f4d3f; } }
  :root[data-theme="dark"]{
    --chrome-bg:#15131c; --chrome-fg:#ded9ec; --chrome-mut:#9a92b0;
    --chrome-line:#2a2637; --accent:#a78bfa;
    --note-bg:#2a1c12; --note-fg:#fdba74; --note-line:#4a2f1a;
    --ok-bg:#0f2620; --ok-fg:#6ee7b7; --ok-line:#1f4d3f; }
  :root[data-theme="light"]{
    --chrome-bg:#eceaf2; --chrome-fg:#3b3550; --chrome-mut:#6f6885;
    --chrome-line:#d8d4e4; --accent:#7c3aed;
    --note-bg:#fff7ed; --note-fg:#9a3412; --note-line:#fed7aa;
    --ok-bg:#ecfdf5; --ok-fg:#065f46; --ok-line:#a7f3d0; }

  body{margin:0;background:var(--chrome-bg);color:var(--chrome-fg);
    font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
  .bar{position:sticky;top:0;z-index:9;background:var(--chrome-bg);
    border-bottom:1px solid var(--chrome-line);padding:12px 20px}
  .bar .in{max-width:760px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:baseline;gap:10px}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);flex:0 0 auto}
  .lbl{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
  .site{font-size:13px;color:var(--chrome-mut);margin-left:auto;font-variant-numeric:tabular-nums}
  .wrap{max-width:760px;margin:0 auto;padding:20px}
  .note{border-radius:10px;padding:11px 14px;font-size:13.5px;line-height:1.6;margin:0 0 12px;
    background:var(--note-bg);color:var(--note-fg);border:1px solid var(--note-line)}
  .note.ok{background:var(--ok-bg);color:var(--ok-fg);border-color:var(--ok-line)}
  /* 블로거는 흰 배경에 렌더된다 — 실제와 같게 보이도록 본문 영역은 라이트 고정 */
  .paper{background:#fff;color:#1f2937;border:1px solid var(--chrome-line);
    border-radius:14px;padding:26px 24px 30px;box-shadow:0 6px 28px rgba(30,20,60,.10);margin-top:8px}
  .ptitle{font-size:26px;font-weight:800;line-height:1.35;margin:0 0 6px;color:#111827;text-wrap:balance}
  .pmeta{font-size:13px;color:#6b7280;padding-bottom:16px;margin-bottom:20px;border-bottom:1px solid #e5e7eb}
  @media (max-width:560px){ .paper{padding:20px 16px 24px} .ptitle{font-size:22px} }
</style>

<div class="bar"><div class="in">
  <span class="dot"></span><span class="lbl">발행 전 미리보기</span>
  <span class="site">eodisanow.blogspot.com</span>
</div></div>

<div class="wrap">
{notes}
  <div class="paper">
    <h1 class="ptitle">{title}</h1>
    <div class="pmeta">어디사 · {date}</div>
{post}
  </div>
</div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    path = args.data if os.path.isabs(args.data) else os.path.join(ROOT, args.data)
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    post_path = os.path.join(ROOT, "blog", "posts", f'{d.get("category","post")}.html')
    with open(post_path, encoding="utf-8") as f:
        post = f.read()

    # 미리보기는 외부 CDN 을 차단하므로 웹폰트가 안 뜬다. 실제 블로거에서는 CDN 링크로 뜨지만,
    # 미리보기에서 폰트가 시스템 폰트로 떨어지면 디자인 판단이 불가능하다.
    # → 글에 실제로 쓰인 글자만 남긴 서브셋을 data URI 로 심는다(각 44KB).
    faces, sub_dir = [], os.path.join(ROOT, "assets", "fonts")
    for wname, weight in (("Regular", 400), ("SemiBold", 600), ("Bold", 700)):
        fp = os.path.join(sub_dir, f"sub-{wname}.woff2")
        if os.path.exists(fp):
            with open(fp, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            faces.append("@font-face{font-family:'Pretendard';font-style:normal;font-weight:%d;"
                         "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2')}"
                         % (weight, b64))
    if faces:
        post = post.replace(
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/pretendard.min.css">',
            "<style>" + "".join(faces) + "</style>")

    # 미리보기(아티팩트)는 외부 호스트를 차단하므로 파트너스 iframe 이 빈 칸으로 뜬다.
    # 깨진 것처럼 보이지 않게 자리표시로 바꾼다 — 실제 블로거에서는 정상 렌더된다.
    n_banner = len(re.findall(r"<iframe[^>]*coupa\.ng[^>]*>\s*</iframe>", post))
    post = re.sub(r"<iframe[^>]*coupa\.ng[^>]*>\s*</iframe>",
                  '<div style="width:120px;height:240px;border:1px dashed #c7c2d8;border-radius:8px;'
                  'display:flex;align-items:center;justify-content:center;text-align:center;'
                  'font-size:11.5px;color:#8b84a3;line-height:1.5;padding:8px;box-sizing:border-box">'
                  '쿠팡 파트너스<br>상품 배너<br><br>(미리보기에서는<br>외부 콘텐츠가<br>차단됩니다)</div>',
                  post)

    items = d.get("items") or []
    linked = [i for i in items if (i.get("link") or "").strip()]
    missing = [i for i in items if not (i.get("link") or "").strip()]

    notes = []
    if n_banner:
        notes.append(f'  <div class="note"><b>파트너스 배너 {n_banner}개</b>는 미리보기에서 점선 상자로 표시됩니다. '
                     f'미리보기 페이지가 외부 콘텐츠를 차단하기 때문이며, <b>실제 블로거에서는 상품 이미지가 정상 표시</b>됩니다.</div>')
    if linked:
        names = ", ".join(i["name"].split()[0] for i in linked)
        notes.append(f'  <div class="note ok"><b>활성 버튼 {len(linked)}개</b> — {html.escape(names)}. '
                     f'실제로 눌리는 제휴 링크입니다.</div>')
    if missing:
        notes.append(f'  <div class="note"><b>비활성 버튼 {len(missing)}개</b> — 제휴 링크가 아직 없어 '
                     f'"링크 준비 중"으로 표시됩니다. 링크를 넣고 다시 생성하면 활성화됩니다.</div>')

    out_html = (SHELL
                .replace("{notes}", "\n".join(notes))
                .replace("{title}", html.escape(d.get("title", "")))
                .replace("{date}", html.escape(d.get("checked_at", "")))
                .replace("{post}", post))

    out = args.out or os.path.join(
        "/tmp/claude-0/-home-user-coupang-partner/bedd4f99-9f58-5846-810c-ebe852448a4d/scratchpad",
        "preview.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"미리보기: {out} · 활성 {len(linked)} / 비활성 {len(missing)}")


if __name__ == "__main__":
    main()
