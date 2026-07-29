#!/usr/bin/env python3
"""블로거용 쇼핑몰별 추천 글 생성기.

posts_data/<id>.json → 블로거 "HTML 보기"에 붙여넣을 HTML.

사용법:
    python3 tools/make_blogpost.py posts_data/feeder.json

설계 근거 (PLAN.md 1-5-1, 1-5-3)
- 당초 "같은 모델 가격비교"로 잡았으나 쿠팡·토스에 겹치는 모델이 거의 없어
  **"쇼핑몰별로 살 만한 것"** 으로 전환했다. 같은 모델인 척하는 게 최악이다.
- 가격은 매일 바뀌고 자동 수집이 불가능하다. 그래서 금액은 확인 날짜와 함께 적되
  글의 본체는 **"어떤 상황이면 어디가 유리한가"** 로 짠다. 가격이 변해도 글이 안 죽는다.
- 효능·성능은 단정하지 않는다. 판매 페이지 표기 인용만.

link 가 비어 있으면 버튼은 자동으로 비활성 처리된다 — 잘못된 유입 방지.
"""
import argparse
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "tools", "blogpost_template.html")
SHOP = {"coupang": ("쿠팡", "c"), "toss": ("토스쇼핑", "t")}


def esc(v):
    return html.escape(str(v), quote=True)


def won(v):
    return f"{int(v):,}원" if isinstance(v, (int, float)) and v else "—"


def net(item):
    """적립을 뺀 실질 부담액. 표시가만 보면 놓치는 부분이라 비교의 축으로 쓴다."""
    p, pt = item.get("price"), item.get("points") or 0
    return p - pt if p else None


def by_platform(items, key):
    return [i for i in items if i.get("platform") == key]


# ---------- 조각 ----------

def build_tldr(items):
    """추천 근거는 데이터에 있는 것만 쓴다.

    가격만 보고 뽑으면 20원 차이로 리뷰 1,098건짜리를 제치고 2건짜리가 올라온다.
    "기능"도 spec 에 실제로 확인된 값이 있을 때만 말한다 — 비싸다고 기능이 많은 게 아니다.
    """
    ok = [i for i in items if i.get("price")]
    if not ok:
        return "<p>가격 정보를 확인하지 못했습니다.</p>"
    out = []

    # 1) 실패 회피 = 리뷰가 가장 두터운 것
    safe = max(ok, key=lambda x: x.get("reviews") or 0)
    if safe.get("reviews"):
        out.append(f'<p>· <b>실패를 피하고 싶다면</b> → {esc(safe["name"])} '
                   f'({SHOP[safe["platform"]][0]} {won(safe["price"])}, 리뷰 {int(safe["reviews"]):,}건)</p>')

    # 2) 가성비 = 최저가. 단 최저가와 5% 이내로 붙은 후보 중 리뷰가 두터운 쪽을 고른다
    lowest = min(i["price"] for i in ok)
    near = [i for i in ok if i["price"] <= lowest * 1.05]
    cheap = max(near, key=lambda x: x.get("reviews") or 0)
    if cheap["name"] != safe["name"]:
        tail = f', 리뷰 {int(cheap["reviews"]):,}건' if cheap.get("reviews") else ""
        out.append(f'<p>· <b>예산을 아끼고 싶다면</b> → {esc(cheap["name"])} '
                   f'({SHOP[cheap["platform"]][0]} {won(cheap["price"])}{tail})</p>')

    # 3) 기능 = spec 에 실제로 확인된 것이 있는 제품만
    featured = [i for i in ok if (i.get("spec") or {}).get("app") or (i.get("spec") or {}).get("camera")]
    if featured:
        f = max(featured, key=lambda x: x["price"])
        feats = [n for n, k in (("앱 연동", "app"), ("카메라", "camera")) if f["spec"].get(k)]
        out.append(f'<p>· <b>{"·".join(feats)}이 필요하다면</b> → {esc(f["name"])} '
                   f'({SHOP[f["platform"]][0]} {won(f["price"])})</p>')

    out.append('<p style="margin-top:12px;color:#6b7280;font-size:14px">'
               '※ 가장 비싼 제품이 기능이 가장 많은 것은 아닙니다. '
               '판매 목록에 사양이 표기되지 않은 제품이 많아, 확인된 것만 적었습니다.</p>')
    return "\n".join(out)


def build_table(items):
    head = ("<table><thead><tr><th>제품</th><th>판매처</th><th>가격</th>"
            "<th>적립</th><th>적립 후</th><th>리뷰</th><th>용량</th></tr></thead><tbody>")
    rows = []
    for i in sorted(items, key=lambda x: x.get("price") or 0):
        label, cls = SHOP[i["platform"]]
        rv = f'{int(i["reviews"]):,}' if i.get("reviews") else "—"
        cap = f'{i["spec"]["capacity_l"]}L' if (i.get("spec") or {}).get("capacity_l") else "—"
        rows.append(
            f'<tr><td class="name">{esc(i["name"])}</td>'
            f'<td><span class="tag {cls}">{label}</span></td>'
            f'<td><b>{won(i.get("price"))}</b></td>'
            f'<td>{won(i.get("points"))}</td>'
            f'<td>{won(net(i))}</td>'
            f'<td>{rv}</td><td>{cap}</td></tr>'
        )
    return head + "".join(rows) + "</tbody></table>"


def build_platform_compare(facts, items):
    c, t = facts.get("coupang", {}), facts.get("toss", {})
    cp, tp = c.get("point_rate"), t.get("point_rate")
    gap = round(tp - cp, 1) if (cp is not None and tp is not None) else None

    # 글에 실은 몇 개가 아니라 "실제로 둘러본 범위"의 최대값을 쓴다.
    # 고른 상품 안에서만 세면 "토스는 최대 2건" 같은 사실과 다른 문장이 나온다.
    cmax = c.get("observed_max_reviews") or max([i.get("reviews") or 0 for i in by_platform(items, "coupang")] or [0])
    tmax = t.get("observed_max_reviews") or max([i.get("reviews") or 0 for i in by_platform(items, "toss")] or [0])

    body = f"""<p>같은 제품이 양쪽에 다 올라오는 경우는 생각보다 드뭅니다. 판매자가 다르기 때문인데,
그래서 "어느 쪽이 싸다"보다 <b>"어느 쪽에서 사는 게 나은가"</b>를 보는 게 실질적입니다.
직접 확인해 보니 차이가 분명한 지점이 세 군데 있었습니다.</p>

<div class="scroll"><table><thead><tr><th></th><th>적립률</th><th>리뷰</th><th>배송</th></tr></thead><tbody>
<tr><td class="name"><span class="tag c">쿠팡</span></td><td><b>{cp}%</b></td>
    <td>{esc(c.get("review_depth", "—"))}</td><td>{esc(c.get("delivery", "—"))}</td></tr>
<tr><td class="name"><span class="tag t">토스쇼핑</span></td><td><b>{tp}%</b></td>
    <td>{esc(t.get("review_depth", "—"))}</td><td>{esc(t.get("delivery", "—"))}</td></tr>
</tbody></table></div>

<h3>① 적립은 토스가 {gap}%p 높습니다</h3>
<p>확인한 상품 전부에서 <b>토스는 {tp}%, 쿠팡은 {cp}%</b>로 일정했습니다.
10만 원짜리를 산다면 {int(100000*tp/100):,}원과 {int(100000*cp/100):,}원, {int(100000*gap/100):,}원 차이입니다.</p>
<p>그래서 계산이 이렇게 됩니다 — <b>토스 표시가가 쿠팡보다 {gap}% 이내로 비싸다면, 적립까지 따졌을 때 토스가 이깁니다.</b>
반대로 그보다 더 비싸면 적립으로 못 메웁니다. 위 표의 '적립 후' 열이 그 계산을 해둔 것입니다.</p>
<p style="color:#6b7280;font-size:14px">※ 양쪽 모두 "최대" 적립 표기라 카드·회원 조건에 따라 실제 금액은 달라질 수 있습니다.</p>

<h3>② 리뷰는 쿠팡이 압도적입니다</h3>
<p>같은 키워드로 양쪽을 훑어보니, 쿠팡은 리뷰가 <b>{cmax:,}건</b>까지 쌓인 제품이 있는 반면
토스에서 가장 많은 것도 <b>{tmax}건</b>이었습니다. 토스쇼핑이 아직 새 서비스라 거래가 덜 쌓인 것으로 보입니다.</p>
<p>자동급식기처럼 <b>고장 나면 반려동물이 굶는</b> 제품에서 리뷰 수는 그냥 숫자가 아닙니다.
처음 사시는 거라면 리뷰가 두꺼운 쪽이 안전합니다.</p>

<h3>③ 급하면 쿠팡입니다</h3>
<p>로켓배송은 오늘 주문하면 내일 옵니다. 토스는 "내일출발" 표기여도 실제 도착은 2~3일 뒤입니다.
사료가 오늘 떨어졌다면 몇 천 원보다 하루가 큽니다.</p>

<div class="who"><b>정리하면</b> — 처음 사거나 급하면 <b>쿠팡</b>, 살 물건을 이미 정했고 며칠 여유가 있다면 적립이 붙는 <b>토스쇼핑</b>이 유리합니다.</div>"""
    return body


def build_items(items, platform):
    label, cls = SHOP[platform]
    out = []
    for i in by_platform(items, platform):
        sp = i.get("spec") or {}
        meta = " · ".join(x for x in [i.get("brand"), i.get("model")] if x) or "모델명 미표기"

        specs = []
        if sp.get("capacity_l"):
            specs.append(f'용량 {sp["capacity_l"]}L')
        if sp.get("app"):
            specs.append("앱 연동")
        if sp.get("camera"):
            specs.append("카메라")
        if sp.get("wet_food"):
            specs.append("습식 가능")
        if sp.get("power"):
            specs.append(esc(sp["power"]))
        if sp.get("food_size_mm"):
            specs.append(f'사료 {esc(sp["food_size_mm"])}')
        if sp.get("washable"):
            specs.append(esc(sp["washable"]))
        specs.append(esc(i.get("delivery", "배송 조건 표기 없음")))

        # 상품평을 확인한 제품은 사람이 정리한 장단점을 그대로 쓴다.
        # 자동 생성 문구는 "확인이 안 됐다"는 말뿐이라 진짜 장단점이 아니다.
        pros = list(i.get("pros") or [])
        cons = list(i.get("cons") or [])
        has_manual = bool(pros or cons)

        if not has_manual:
            if (i.get("reviews") or 0) >= 500:
                pros.append(f'리뷰 {int(i["reviews"]):,}건 · 평점 {i.get("rating")} — 검증이 충분합니다')
            elif i.get("reviews"):
                cons.append(f'리뷰가 {int(i["reviews"])}건뿐이라 판단할 근거가 얇습니다')
            else:
                cons.append("리뷰 수가 표기되지 않아 검증이 어렵습니다")
            if sp.get("app"):
                pros.append("밖에서 급여 시간·양을 바꿀 수 있습니다")
            if sp.get("camera"):
                pros.append("먹는 모습을 확인할 수 있습니다")
            if not sp.get("capacity_l"):
                cons.append("목록에 용량 표기가 없어 상세페이지 확인이 필요합니다")
            if not sp.get("blackout_backup"):
                cons.append("정전 대비 여부가 확인되지 않았습니다 — 오래 집을 비운다면 꼭 확인하세요")


        url = (i.get("link") or "").strip()
        btn = (f'<a class="btn {cls}" href="{esc(url)}" target="_blank" rel="noopener nofollow sponsored">{label}에서 보기</a>'
               if url else f'<span class="btn off">{label} 링크 준비 중</span>')

        insight_html = (f'<div class="insight"><b>리뷰를 보면</b> {i["review_insight"]}</div>'
                        if i.get("review_insight") else "")
        note_html = (f'<div class="who">ℹ️ {i["note"]}</div>' if i.get("note") else "")
        # 배너는 파트너스가 제공하는 공식 위젯 코드를 그대로 넣는다(이미지·가격·링크 포함).
        # 상품 이미지를 직접 퍼오는 것과 달리 정책상 허용되는 방식이다.
        banner_html = (f'<div class="banner">{i["banner"]}</div>' if i.get("banner") else "")

        ptxt = f'<p class="price">{won(i.get("price"))}'
        if i.get("list_price"):
            ptxt += f'<s>{won(i["list_price"])}</s>'
        ptxt += "</p>"
        pt = (f'<p class="pt">적립 {won(i.get("points"))} → 실질 {won(net(i))}</p>'
              if i.get("points") else "")

        out.append(f"""<div class="card">
<h3>{esc(i["name"])}</h3>
<p class="meta">{esc(meta)}</p>
<div class="head">
{banner_html}
<div class="headinfo">{ptxt}{pt}<p class="spec">{" · ".join(specs)}</p></div>
</div>
<ul class="pro">{"".join(f"<li>{p}</li>" for p in pros)}</ul>
<ul class="con">{"".join(f"<li>{c}</li>" for c in cons)}</ul>
{insight_html}
{note_html}
{btn}
</div>""")
    return "\n".join(out) or "<p>해당 쇼핑몰에서 고른 상품이 없습니다.</p>"


CRITERIA = """<ul>
<li><b>정전 대비</b> — 여기서 갈립니다. 어댑터 전용이면 코드가 빠지거나 정전됐을 때 급여가 멈춥니다. 하루 종일 집을 비운다면 배터리를 함께 쓰는 제품을 보세요. <b>판매 목록에는 거의 표기되지 않으니 상세페이지에서 직접 확인해야 합니다.</b></li>
<li><b>세척</b> — 사료 통로에 기름과 가루가 낍니다. 분리해서 씻을 수 있는지가 6개월 뒤 만족도를 가릅니다. 통째로 못 씻는 제품은 결국 안 쓰게 됩니다.</li>
<li><b>사료 알갱이 크기</b> — 크면 통로에 걸립니다. 지금 주시는 사료와 제조사 권장 크기를 맞춰 보세요.</li>
<li><b>습식 여부</b> — 대부분 건사료 전용입니다. 습식을 주신다면 애초에 다른 제품군을 찾으셔야 합니다.</li>
<li><b>용량</b> — 클수록 좋은 게 아닙니다. 사료는 개봉하면 산패됩니다. <b>2~3주에 다 먹을 양</b>이 적당합니다.</li>
<li><b>소음</b> — 배출 모터 소리에 예민한 아이들이 있습니다. 표기값이 있으면 참고하되 체감은 환경에 따라 다릅니다.</li>
</ul>"""

FAQ = [
    ("자동급식기, 정말 필요한가요?",
     "출퇴근이 불규칙하거나 집을 오래 비우는 날이 있다면 값을 합니다. 매일 같은 시간에 계신다면 굳이 필요하지 않습니다."),
    ("정전되면 사료가 안 나오나요?",
     "어댑터 전용 제품은 그렇습니다. 배터리를 함께 쓰는 제품은 정전 중에도 예약 급여가 유지됩니다. 다만 이 정보는 판매 목록에 잘 안 나오니 상세페이지에서 확인하셔야 합니다."),
    ("습식 사료도 넣을 수 있나요?",
     "대부분 건사료 전용입니다. 습식은 통로에 들러붙고 상하기 때문에 습식 전용 급여기를 따로 찾으셔야 합니다."),
    ("쿠팡과 토스쇼핑 중 어디가 싼가요?",
     "같은 제품이 양쪽에 다 있는 경우가 드물어 단순 비교가 어렵습니다. 다만 적립률은 토스가 7%, 쿠팡이 5%로 일정했습니다. 표시가 차이가 2% 이내라면 적립까지 따져 토스가 유리합니다."),
    ("리뷰가 적은 제품은 피해야 하나요?",
     "무조건 그렇진 않지만, 자동급식기는 고장 나면 반려동물이 굶는 제품입니다. 처음 사시는 거라면 리뷰가 두꺼운 쪽을 권합니다."),
]


def build_faq():
    return "\n".join(f'<div class="faq"><b>Q. {q}</b>{a}</div>' for q, a in FAQ)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out")
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
        "platform_compare": build_platform_compare(d.get("platform_facts") or {}, items),
        "coupang_items": build_items(items, "coupang"),
        "toss_items": build_items(items, "toss"),
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

    print(f'생성: {out} ({len(out_html):,}자)')
    print(f'제목 후보: {d.get("title", "")}')
    missing = [i["name"] for i in items if not (i.get("link") or "").strip()]
    if missing:
        print(f"\n⚠️  제휴 링크 미입력 {len(missing)}개 → 버튼이 비활성 상태입니다:")
        for m in missing:
            print("   -", m)


if __name__ == "__main__":
    main()
