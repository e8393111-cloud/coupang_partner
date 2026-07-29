#!/usr/bin/env python3
"""블로거용 가격비교 글 생성기.

확장 클로드가 수집해 온 JSON(blog/collect_prompt.md 형식) → 블로거에 붙여넣을 HTML.

사용법:
    python3 tools/make_blogpost.py posts_data/feeder.json
    python3 tools/make_blogpost.py posts_data/feeder.json --out blog/posts/feeder.html

설계 원칙 (PLAN.md 1-5-1)
- **금액이 아니라 판단 기준이 본체**다. 가격은 확인 날짜와 함께 적고,
  글의 뼈대는 "어떤 상황이면 어디가 유리한가"로 만든다. 그래야 가격이 바뀌어도 안 죽는다.
- 가격만 비교하면 정직하지 않다. **가격·배송·혜택 3축**으로 본다.
- 효능은 단정하지 않는다. 제조사 표기 인용만.

링크가 아직 없으면(빈 문자열) 버튼은 자동으로 비활성 처리된다 — 잘못된 유입 방지.
"""
import argparse
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "tools", "blogpost_template.html")


def esc(v):
    return html.escape(str(v), quote=True)


def won(v):
    return f"{int(v):,}원" if isinstance(v, (int, float)) and v else "—"


def shop(item, key):
    """쿠팡/토스 블록을 안전하게 꺼낸다(없거나 null 이면 빈 dict)."""
    d = item.get(key) or {}
    return d if isinstance(d, dict) else {}


def price_of(item, key):
    p = shop(item, key).get("price")
    return p if isinstance(p, (int, float)) and p > 0 else None


def cheaper(item):
    """(승자, 차액, 차액비율%) — 한쪽만 있으면 승자 None."""
    c, t = price_of(item, "coupang"), price_of(item, "toss")
    if c is None or t is None:
        return None, None, None
    if c == t:
        return "same", 0, 0.0
    lo, hi = min(c, t), max(c, t)
    return ("toss" if t < c else "coupang"), hi - lo, round((hi - lo) / hi * 100, 1)


def sellable(item):
    """토스에서 실제로 수익이 나는 상품인가 (쉐어링크 발급 가능 여부)."""
    return bool(shop(item, "toss").get("sharelink_available"))


# ---------- 조각 생성 ----------

def build_tldr(items):
    priced = [i for i in items if price_of(i, "coupang") or price_of(i, "toss")]
    if not priced:
        return "<p>가격 정보를 확인하지 못했습니다.</p>"

    def low(i):
        ps = [p for p in (price_of(i, "coupang"), price_of(i, "toss")) if p]
        return min(ps) if ps else 10**9

    ordered = sorted(priced, key=low)
    cheap, premium = ordered[0], ordered[-1]
    mid = ordered[len(ordered) // 2]
    rows = [
        ("예산을 아끼고 싶다면", cheap),
        ("무난하게 오래 쓰려면", mid),
        ("기능을 다 갖추고 싶다면", premium),
    ]
    out, seen = [], set()
    for label, it in rows:
        if it["name"] in seen:
            continue
        seen.add(it["name"])
        out.append(f'<p>· {label} → <b>{esc(it["name"])}</b> ({won(low(it))}~)</p>')
    return "\n".join(out)


def build_table(items):
    head = ("<table><thead><tr><th>제품</th><th>쿠팡</th><th>토스쇼핑</th>"
            "<th>차액</th><th>용량</th><th>정전 대비</th></tr></thead><tbody>")
    rows = []
    for i in items:
        c, t = price_of(i, "coupang"), price_of(i, "toss")
        w, diff, pct = cheaper(i)
        ccls = ' class="win"' if w == "coupang" else ""
        tcls = ' class="win"' if w == "toss" else ""
        if w in (None, "same"):
            gap = "—" if w is None else "동일"
        else:
            gap = f"{won(diff)} ({pct}%)"
        sp = i.get("spec") or {}
        cap = f'{sp["capacity_l"]}L' if sp.get("capacity_l") else "—"
        bk = "○" if sp.get("blackout_backup") else "✕"
        rows.append(
            f'<tr><td class="name">{esc(i["name"])}</td>'
            f'<td{ccls}>{won(c)}</td><td{tcls}>{won(t) if t else "미판매"}</td>'
            f'<td>{gap}</td><td>{cap}</td><td>{bk}</td></tr>'
        )
    return head + "".join(rows) + "</tbody></table>"


def build_price_summary(items, checked_at):
    pcts = [p for _, _, p in map(cheaper, items) if p]
    wins = [w for w, _, _ in map(cheaper, items) if w in ("coupang", "toss")]
    if not pcts:
        return f"※ {esc(checked_at)} 기준. 양쪽 모두에서 판매되는 상품이 적어 가격 비교는 참고용입니다."
    avg = round(sum(pcts) / len(pcts), 1)
    t, c = wins.count("toss"), wins.count("coupang")
    side = "토스쇼핑" if t > c else ("쿠팡" if c > t else "양쪽이 비슷")
    if side == "양쪽이 비슷":
        body = "제품마다 유리한 쪽이 갈립니다"
    else:
        body = f"{len(wins)}개 중 {max(t, c)}개에서 <b>{side}</b>가 저렴했고, 평균 차이는 <b>{avg}%</b>였습니다"
    return f"※ {esc(checked_at)} 기준 · {body}. 가격은 자주 바뀌니 반드시 실제 페이지에서 확인하세요."


def build_where(items):
    """가격·배송·혜택 3축. 가격이 바뀌어도 죽지 않는 '판단 기준' 문단."""
    rocket = sum(1 for i in items if shop(i, "coupang").get("rocket"))
    return f"""<p>가격만 보면 반쪽짜리 비교입니다. 세 가지를 같이 봐야 합니다.</p>
<div class="scroll"><table><thead><tr><th></th><th>가격</th><th>배송</th><th>혜택</th></tr></thead><tbody>
<tr><td class="name">쿠팡</td><td>제품별로 갈림</td><td>로켓배송 {rocket}개 — 빠름</td><td>와우 회원 혜택</td></tr>
<tr><td class="name">토스쇼핑</td><td>제품별로 갈림</td><td>판매자 배송 — 상품마다 다름</td><td>토스 포인트·쿠폰</td></tr>
</tbody></table></div>
<ul>
<li><b>급하게 필요하다</b> → 쿠팡. 로켓배송이면 하루 차이가 납니다. 몇 천 원보다 하루가 중요할 때가 많습니다.</li>
<li><b>며칠 기다릴 수 있다</b> → 양쪽 가격을 비교해서 싼 쪽. 위 표의 차액을 보세요.</li>
<li><b>이미 회원이다</b> → 와우 회원이면 쿠팡, 토스를 자주 쓰면 포인트까지 계산해 보세요. 표시가격만으로는 안 보이는 부분입니다.</li>
</ul>"""


def build_items(items):
    out = []
    for idx, i in enumerate(items, 1):
        sp = i.get("spec") or {}
        c, t = shop(i, "coupang"), shop(i, "toss")
        meta = " · ".join(x for x in [i.get("brand"), i.get("model")] if x) or "모델명 미확인"

        specs = []
        if sp.get("capacity_l"):
            specs.append(f'용량 {sp["capacity_l"]}L')
        if sp.get("power"):
            specs.append(f'전원 {esc(sp["power"])}')
        specs.append("정전 대비 " + ("가능" if sp.get("blackout_backup") else "확인 필요"))
        specs.append("습식사료 " + ("가능" if sp.get("wet_food") else "불가"))
        if sp.get("app"):
            specs.append("앱 연동")
        if sp.get("camera"):
            specs.append("카메라 내장")
        if sp.get("washable"):
            specs.append(f'세척 {esc(sp["washable"])}')
        if sp.get("noise_db"):
            specs.append(f'소음 {sp["noise_db"]}dB (제조사 표기)')

        pros, cons = [], []
        if sp.get("blackout_backup"):
            pros.append("정전이나 코드 빠짐에도 급여가 멈추지 않습니다")
        else:
            cons.append("정전 대비가 확인되지 않았습니다 — 장시간 외출이 잦다면 확인이 필요합니다")
        if sp.get("app"):
            pros.append("앱으로 급여 시간·양을 밖에서 바꿀 수 있습니다")
        if sp.get("camera"):
            pros.append("카메라가 있어 먹는 모습을 확인할 수 있습니다")
        if not sp.get("wet_food"):
            cons.append("건사료 전용입니다 — 습식을 주신다면 맞지 않습니다")
        if c.get("reviews"):
            pros.append(f'쿠팡 리뷰 {int(c["reviews"]):,}개 (평점 {c.get("rating", "—")})')
        if t.get("price") and not sellable(i):
            cons.append("토스쇼핑에서는 재고·판매 상태가 바뀔 수 있습니다")
        if i.get("note"):
            cons.append(esc(i["note"]))

        w, diff, pct = cheaper(i)
        if w == "toss":
            who = f'양쪽 다 있다면 <b>토스쇼핑이 {won(diff)} 저렴</b>합니다. 급하지 않다면 이쪽.'
        elif w == "coupang":
            who = f'<b>쿠팡이 {won(diff)} 저렴</b>합니다. 로켓배송까지 되면 고민할 이유가 없습니다.'
        elif w == "same":
            who = "가격이 같습니다. 배송 속도로 고르세요."
        else:
            who = "한쪽에서만 판매 중이라 가격 비교는 불가합니다."

        links = i.get("links") or {}
        btns = []
        for key, label, cls in (("toss", "토스쇼핑에서 보기", "t"), ("coupang", "쿠팡에서 보기", "c")):
            url = (links.get(key) or "").strip()
            if not price_of(i, key):
                continue
            if url:
                btns.append(f'<a class="btn {cls}" href="{esc(url)}" target="_blank" rel="noopener nofollow sponsored">{label}</a>')
            else:
                btns.append(f'<span class="btn off">{label} (링크 준비 중)</span>')

        out.append(f"""<div class="card">
<h3>{idx}. {esc(i["name"])}</h3>
<p class="meta">{esc(meta)}</p>
<p>{" · ".join(specs)}</p>
<ul class="pro">{"".join(f"<li>{p}</li>" for p in pros)}</ul>
<ul class="con">{"".join(f"<li>{c_}</li>" for c_ in cons)}</ul>
<div class="who">👉 {who}</div>
<div class="btns">{"".join(btns)}</div>
</div>""")
    return "\n".join(out)


CRITERIA = """<ul>
<li><b>정전 대비</b> — 여기서 갈립니다. 어댑터 전용이면 코드가 빠지거나 정전됐을 때 급여가 멈춥니다. 하루 종일 집을 비운다면 배터리 겸용을 보세요.</li>
<li><b>세척</b> — 사료 통로에 기름과 가루가 낍니다. <b>분리해서 물로 씻을 수 있는지</b>가 6개월 뒤 만족도를 가릅니다. 통째로 못 씻는 제품은 결국 안 쓰게 됩니다.</li>
<li><b>사료 크기</b> — 알갱이가 크면 통로에 걸립니다. 지금 주시는 사료 크기와 제조사 권장 크기를 맞춰 보세요.</li>
<li><b>습식 여부</b> — 대부분 건사료 전용입니다. 습식을 주신다면 애초에 다른 제품군을 봐야 합니다.</li>
<li><b>소음</b> — 배출 모터 소리에 예민한 아이들이 있습니다. 표기값이 있으면 참고하되, 실제 체감은 환경에 따라 다릅니다.</li>
<li><b>용량</b> — 클수록 좋은 게 아닙니다. 사료는 개봉 후 산패됩니다. <b>2~3주에 다 먹을 양</b>이 적당합니다.</li>
</ul>"""

FAQ = [
    ("자동급식기, 정말 필요한가요?",
     "출퇴근 시간이 불규칙하거나 집을 오래 비우는 날이 있다면 값을 합니다. 매일 같은 시간에 집에 계신다면 굳이 필요하지 않습니다."),
    ("정전되면 사료가 안 나오나요?",
     "어댑터 전용 제품은 그렇습니다. 배터리를 함께 쓰는 제품은 정전 중에도 예약 급여가 유지됩니다. 위 비교표의 '정전 대비' 항목을 보세요."),
    ("습식 사료도 넣을 수 있나요?",
     "대부분 건사료 전용입니다. 습식은 통로에 들러붙고 상하기 때문에 별도의 습식 전용 급여기를 찾으셔야 합니다."),
    ("쿠팡과 토스쇼핑, 어디가 더 싼가요?",
     "제품마다 다릅니다. 위 비교표에 확인 날짜와 함께 정리해 뒀습니다. 다만 가격은 자주 바뀌니 구매 직전에 양쪽을 다시 확인하시는 게 확실합니다."),
    ("같은 모델이 맞나요?",
     "모델명이 확인된 것만 비교했습니다. 확인이 어려운 경우는 표에 그렇게 적어 뒀습니다. 구매 전 상세페이지의 모델명을 한 번 더 확인해 주세요."),
]


def build_faq():
    return "\n".join(f'<div class="faq"><b>Q. {q}</b>{a}</div>' for q, a in FAQ)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="수집 JSON 경로")
    ap.add_argument("--out", help="출력 HTML 경로 (기본: blog/posts/<category>.html)")
    args = ap.parse_args()

    path = args.data if os.path.isabs(args.data) else os.path.join(ROOT, args.data)
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    items = d.get("items") or []
    if not items:
        raise SystemExit("items 가 비어 있습니다")

    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()

    tokens = {
        "checked_at": esc(d.get("checked_at", "")),
        "tldr": build_tldr(items),
        "table": build_table(items),
        "price_summary": build_price_summary(items, d.get("checked_at", "")),
        "where": build_where(items),
        "items": build_items(items),
        "criteria": CRITERIA,
        "faq": build_faq(),
    }
    out_html = tpl
    for k, v in tokens.items():
        out_html = out_html.replace("{{%s}}" % k, v)
    if "{{" in out_html:
        raise SystemExit("치환 안 된 토큰: " + out_html.split("{{", 1)[1][:40])

    out = args.out or os.path.join("blog", "posts", f'{d.get("category", "post")}.html')
    out = out if os.path.isabs(out) else os.path.join(ROOT, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(out_html)

    print("생성:", out, f"({len(out_html):,}자)")
    missing = [i["name"] for i in items if not (i.get("links") or {}).get("toss")
               and not (i.get("links") or {}).get("coupang")]
    if missing:
        print(f"⚠️  제휴 링크 미입력 {len(missing)}개 → 해당 버튼은 비활성 상태입니다:")
        for m in missing:
            print("   -", m)
        print("   JSON 의 각 항목에 \"links\": {\"toss\":\"...\", \"coupang\":\"...\"} 를 넣고 다시 실행하세요.")
    nosl = [i["name"] for i in items if price_of(i, "toss") and not sellable(i)]
    if nosl:
        print(f"⚠️  토스 쉐어링크 발급 불가(수익 0원) 상품 {len(nosl)}개:", ", ".join(nosl))


if __name__ == "__main__":
    main()
