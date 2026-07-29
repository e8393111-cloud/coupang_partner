#!/usr/bin/env python3
"""블로거용 쇼핑몰별 추천 글 생성기.

posts_data/<id>.json → 블로거 "HTML 보기"에 붙여넣을 HTML.

사용법:
    python3 tools/make_blogpost.py posts_data/feeder.json

설계 근거 (PLAN.md 1-5-1, 1-5-3)
- "같은 모델 가격비교"는 쿠팡·토스에 겹치는 모델이 거의 없어 성립하지 않았다.
  **"쇼핑몰별로 살 만한 것"** 으로 간다. 같은 모델인 척하는 게 최악이다.
- 가격은 매일 바뀌고 자동 수집이 불가능하다. 금액은 확인 날짜와 함께 적되
  글의 본체는 **"어떤 상황이면 어디가 유리한가"** 로 짠다.
- 효능·성능은 단정하지 않는다. 판매 페이지 표기와 구매자 후기 인용만.

디자인 원칙 (2026-07-29 전면 개편)
- **딥 그린을 지면색, 앰버를 포인트로.** 판매처(쿠팡 빨강·토스 파랑)는 그 둘과 겹치지 않아
  같은 화면에서 "브랜드 색"과 "데이터 색"이 헷갈리지 않는다.
- 카드·둥근 모서리·이모지를 쓰지 않는다. 구분선과 여백, 타이포 위계로 구조를 만든다.
- 숫자는 tabular-nums 로 자릿수를 맞추고 우측 정렬한다.

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
    """반자동(중력식)은 목적이 달라 본 목록에서 빼고 별도 섹션으로 다룬다."""
    return [i for i in items if i.get("platform") == key and i.get("product_type") != "semi"]


def semi_items(items):
    return [i for i in items if i.get("product_type") == "semi"]


def src_tag(platform):
    label, cls = SHOP[platform]
    return f'<span class="src {cls}">{label}</span>'


# ---------- 도입 · 대표 추천 ----------

def build_intro(d):
    """왜 이게 필요한지 한 문단. 검색자 절반은 '살까 말까' 단계다."""
    txt = d.get("intro")
    return f'<p class="intro">{txt}</p>' if txt else ""


def build_toppick(d, items):
    """고민하는 사람에게 딱 하나 밀어준다. 조건별 나열은 결정을 미루게 한다."""
    tp = d.get("top_pick")
    if not tp:
        return ""
    match = next((i for i in items if i["name"] == tp["name"]), None)
    price = won(match.get("price")) if match else ""
    plat = SHOP.get(tp.get("platform", ""), ("", ""))
    tag = src_tag(tp["platform"]) if tp.get("platform") else ""
    sub = f'{tag} · {price}' if price else tag
    return (f'<div class="pick"><div class="picklabel">고민된다면, 이것</div>'
            f'<div class="pickname">{esc(tp["name"])}</div>'
            f'<div class="picksub">{sub}</div>'
            f'<p class="pickwhy">{tp["why"]}</p></div>')


# ---------- 결론 ----------

def build_tldr(all_items):
    items = [i for i in all_items if i.get("product_type") != "semi"]
    """추천 근거는 데이터에 있는 것만 쓴다.

    가격만 보고 뽑으면 20원 차이로 리뷰 1,098건짜리를 제치고 2건짜리가 올라온다.
    "기능"도 spec 에 실제로 확인된 값이 있을 때만 말한다 — 비싸다고 기능이 많은 게 아니다.
    """
    ok = [i for i in items if i.get("price")]
    if not ok:
        return '<p>가격 정보를 확인하지 못했습니다.</p>'
    rows, used = [], set()

    def row(k, it, extra=""):
        used.add(it["name"])
        rows.append(
            f'<div class="row"><div class="k">{k}</div>'
            f'<div class="v">{esc(it["name"])}<br>'
            f'<em>{src_tag(it["platform"])} · {won(it["price"])}{extra}</em></div></div>')

    safe = max(ok, key=lambda x: x.get("reviews") or 0)
    if safe.get("reviews"):
        row("실패를 피하려면", safe, f' · 후기 {int(safe["reviews"]):,}건')

    lowest = min(i["price"] for i in ok)
    near = [i for i in ok if i["price"] <= lowest * 1.05]
    cheap = max(near, key=lambda x: x.get("reviews") or 0)
    if cheap["name"] not in used:
        tail = f' · 후기 {int(cheap["reviews"]):,}건' if cheap.get("reviews") else ""
        row("가장 저렴한 쪽", cheap, tail)

    featured = [i for i in ok if (i.get("spec") or {}).get("app") or (i.get("spec") or {}).get("camera")]
    if featured:
        f = max(featured, key=lambda x: x["price"])
        if f["name"] not in used:
            feats = [n for n, k in (("앱 연동", "app"), ("카메라", "camera")) if f["spec"].get(k)]
            row(f'{"·".join(feats)}이 필요하면', f)

    rest = [i for i in ok if i["name"] not in used]
    if rest:
        r = max(rest, key=lambda x: x["price"])
        row("예산이 넉넉하면", r)

    return ('<div class="lede">' + "".join(rows) + '</div>'
            '<p class="caveat">가장 비싼 제품이 기능이 가장 많은 것은 아닙니다. '
            '판매 목록에 사양이 표기되지 않은 제품이 많아, 확인된 항목만 적었습니다.</p>')


# ---------- 표 ----------

def build_table(all_items):
    items = [i for i in all_items if i.get("product_type") != "semi"]
    head = ('<table><thead><tr><th>제품</th><th>판매처</th><th>가격</th>'
            '<th>적립</th><th>적립 후</th><th>후기</th><th>용량</th></tr></thead><tbody>')
    rows = []
    for i in sorted(items, key=lambda x: x.get("price") or 0):
        rv = f'{int(i["reviews"]):,}건' if i.get("reviews") else "—"
        cap = f'{i["spec"]["capacity_l"]}L' if (i.get("spec") or {}).get("capacity_l") else "—"
        rows.append(
            f'<tr><td>{esc(i["name"])}</td>'
            f'<td>{src_tag(i["platform"])}</td>'
            f'<td class="num">{won(i.get("price"))}</td>'
            f'<td class="dim">{won(i.get("points"))}</td>'
            f'<td class="num">{won(net(i))}</td>'
            f'<td class="dim">{rv}</td><td class="dim">{cap}</td></tr>')
    return head + "".join(rows) + "</tbody></table>"


# ---------- 맞대결 ----------

def build_headtohead(items):
    """양쪽에서 가격이 거의 같은 두 제품이 있으면 그 대결을 전면에 세운다.

    적립률 차이를 추상적으로 설명하는 것보다, 거의 같은 값의 두 제품을 나란히 두고
    "적립까지 따지면 뒤집히는데 후기 수는 이만큼 차이난다"를 보여주는 편이 훨씬 잘 읽힌다.
    데이터가 그렇게 나올 때만 넣는다.
    """
    c = [i for i in by_platform(items, "coupang") if i.get("price")]
    t = [i for i in by_platform(items, "toss") if i.get("price")]
    if not c or not t:
        return ""
    a, b = min(c, key=lambda x: x["price"]), min(t, key=lambda x: x["price"])
    gap = abs(a["price"] - b["price"])
    if gap > min(a["price"], b["price"]) * 0.05:
        return ""

    na, nb = net(a), net(b)
    winner, diff = (a, nb - na) if na < nb else (b, na - nb)
    ar = int(a.get("reviews") or 0)
    br = int(b.get("reviews") or 0)

    def col(it, align_end=False):
        rv = f'후기 {int(it["reviews"]):,}건' if it.get("reviews") else "후기 표기 없음"
        return (f'<div class="vscol">{src_tag(it["platform"])}'
                f'<div class="vsname">{esc(it["name"])}</div>'
                f'<div class="vsbig">{won(net(it))}</div>'
                f'<div class="vssub">표시가 {won(it["price"])} − 적립 {won(it.get("points"))}<br>{rv}</div></div>')

    if ar and br:
        ratio = f'후기는 <b>{max(ar, br):,}건 대 {min(ar, br):,}건</b>입니다. '
    else:
        ratio = ""

    verdict = (f'표시가는 <b>{won(gap)}</b> 차이인데, 적립까지 넣으면 '
               f'<b>{SHOP[winner["platform"]][0]}이 {won(diff)} 저렴</b>해집니다. '
               f'{ratio}'
               f'{won(diff)}을 아끼려고 검증이 덜 된 쪽을 고를 것인가 — '
               f'이 글에서 가장 현실적인 선택입니다. '
               f'처음 쓰시는 거라면 후기가 두꺼운 쪽을, 이미 어떤 제품인지 아신다면 적립이 붙는 쪽을 권합니다.')

    return ('<h2>거의 같은 값, 다른 선택</h2>'
            '<div class="vs"><div class="vsgrid">'
            + col(a) + '<div class="vsmid">vs</div>' + col(b) +
            '</div></div>'
            f'<p class="vsverdict">{verdict}</p>')


def build_blackout(items):
    """정전 대비를 제품마다 반복하면 불안만 4번 심는다. 한 곳에 정리하면 정보가 된다."""
    yes = [i for i in items if (i.get("spec") or {}).get("blackout_backup")]
    if not yes:
        return ""
    names = ", ".join(i["name"].split()[0] for i in yes)
    return (f'<div class="tip"><b>정전·정전 대비</b>는 여기서 갈립니다. '
            f'이번 4개 중 코드가 빠지거나 정전돼도 급여가 이어지는 건 '
            f'<b>{names}</b>(건전지 겸용)뿐입니다. 나머지는 어댑터 전용이거나 판매 목록에 표기가 없어, '
            f'오래 집을 비우는 집이라면 상세페이지에서 배터리 지원을 꼭 확인하세요.</div>')


# ---------- 표 아래 캡션 ----------

def build_table_note(facts, items):
    """플랫폼 차이를 별도 섹션으로 설명하지 않고 표 바로 밑에 붙인다.

    독자는 비교하러 왔지 플랫폼 경제학 강의를 들으러 온 게 아니다.
    같은 정보라도 "지금 표를 보고 있는 자리"에 있어야 판단에 쓰인다.
    """
    c, t = facts.get("coupang", {}), facts.get("toss", {})
    cp, tp = c.get("point_rate"), t.get("point_rate")
    if cp is None or tp is None:
        return ""
    gap = round(tp - cp, 1)
    cmax = c.get("observed_max_reviews") or 0
    tmax = t.get("observed_max_reviews") or 0

    lines = [f'<b>적립</b> 토스 {tp}% · 쿠팡 {cp}%로 일정했습니다. '
             f'표시가 차이가 {gap}% 이내면 적립까지 따져 토스가 유리합니다 — '
             f"'적립 후' 열이 그 계산입니다."]
    if cmax and tmax:
        lines.append(f'<b>후기</b> 쿠팡은 {cmax:,}건까지 쌓인 제품이 있고, 토스는 가장 많은 것도 {tmax}건이었습니다.')
    lines.append(f'<b>배송</b> {esc(c.get("delivery", "—"))} · 토스는 {esc(t.get("delivery", "—"))}.')
    lines.append('적립은 양쪽 다 "최대" 표기라 카드·회원 조건에 따라 달라질 수 있습니다.')
    return '<p class="tnote">' + "<br>".join(lines) + "</p>"


# ---------- 제품 ----------

def render_item(i):
    """제품 카드 하나. 본 목록과 반자동 섹션이 같은 렌더러를 쓴다."""
    label, cls = SHOP[i["platform"]]
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

    # 후기를 확인한 제품은 사람이 정리한 장단점을 쓴다.
    # 자동 문구는 "확인이 안 됐다"는 말뿐이라 진짜 장단점이 아니다.
    pros = list(i.get("pros") or [])
    cons = list(i.get("cons") or [])
    if not (pros or cons):
        if (i.get("reviews") or 0) >= 500:
            pros.append(f'후기 {int(i["reviews"]):,}건 · 평점 {i.get("rating")} — 검증이 충분합니다')
        elif i.get("reviews"):
            cons.append(f'후기가 {int(i["reviews"])}건뿐이라 판단할 근거가 얇습니다')
        else:
            cons.append("후기 수가 표기되지 않아 검증이 어렵습니다")
        if sp.get("app"):
            pros.append("밖에서 급여 시간·양을 바꿀 수 있습니다")
        if sp.get("camera"):
            pros.append("먹는 모습을 확인할 수 있습니다")
        if not sp.get("capacity_l"):
            cons.append("목록에 용량 표기가 없어 상세페이지 확인이 필요합니다")
        # 정전 대비는 build_blackout 이 한 곳에 정리하므로 카드마다 반복하지 않는다

    pc = '<div class="pc">'
    pc += ('<div class="pcbox good"><div class="pclabel">좋은 점</div><ul>'
           + "".join(f"<li>{p}</li>" for p in pros) + "</ul></div>") if pros else ""
    pc += ('<div class="pcbox bad"><div class="pclabel">아쉬운 점</div><ul>'
           + "".join(f"<li>{c}</li>" for c in cons) + "</ul></div>") if cons else ""
    pc += "</div>"

    quote = (f'<div class="quote"><span class="qh">후기를 보면</span>{i["review_insight"]}</div>'
             if i.get("review_insight") else "")
    reason = (f'<div class="reason"><b>이럴 때 이 제품</b> {i["buy_reason"]}</div>'
              if i.get("buy_reason") else "")
    aside = f'<p class="aside">{i["note"]}</p>' if i.get("note") else ""
    # 배너는 파트너스 공식 위젯 코드를 그대로 넣는다(이미지·가격·링크 포함).
    # 상품 이미지를 직접 퍼오는 것과 달리 정책상 허용되는 방식이다.
    banner = f'<div class="banner">{i["banner"]}</div>' if i.get("banner") else ""

    url = (i.get("link") or "").strip()
    buy = (f'<a class="buy {cls}" href="{esc(url)}" target="_blank" rel="noopener nofollow sponsored">'
           f'{label}에서 보기</a>'
           if url else f'<span class="buy off">{label} 링크 준비 중</span>')

    price = f'<p class="iprice">{won(i.get("price"))}'
    if i.get("list_price"):
        price += f'<s>{won(i["list_price"])}</s>'
    price += "</p>"
    rate = ""
    if i.get("points") and i.get("price"):
        rate = f' ({round(i["points"] / i["price"] * 100):.0f}%)'
    pts = (f'<p class="ipt">적립 {won(i.get("points"))}{rate} · 실질 부담 {won(net(i))}</p>'
           if i.get("points") else "")

    return (f"""<div class="item">
<h3>{esc(i["name"])}</h3>
<p class="imeta">{esc(meta)}</p>
<div class="ihead">{banner}<div class="iinfo">{price}{pts}
<p class="ispec">{" · ".join(specs)}</p></div></div>
{pc}{quote}{reason}{aside}{buy}
</div>""")


def build_items(items, platform):
    rows = by_platform(items, platform)
    return "\n".join(render_item(i) for i in rows) or "<p>해당 쇼핑몰에서 고른 상품이 없습니다.</p>"


def build_toss_block(items, d):
    """토스에 본 목록감이 없으면 그 사실을 섹션으로 밝힌다.

    "해당 쇼핑몰에서 고른 상품이 없습니다" 한 줄로 넘기면 성의가 없어 보이고,
    검증 안 된 제품을 억지로 채우면 글이 스스로 세운 기준을 어긴다.
    없는 이유를 쓰는 게 셋 중 제일 정직하고 제일 읽을 만하다.
    """
    rows = by_platform(items, "toss")
    if rows:
        note = f'<p class="tossnote">{d["toss_note"]}</p>' if d.get("toss_note") else ""
        return ('<h2>토스쇼핑에서 살 만한 것</h2>' + note
                + "\n".join(render_item(i) for i in rows))
    skip = d.get("toss_skip")
    if not skip:
        return ""
    return f'<h2>토스쇼핑은 이번에 뺐습니다</h2><p class="tossnote">{skip}</p>'


def build_semi(items, note):
    rows = semi_items(items)
    if not rows:
        return ""
    body = "".join(render_item(i) for i in rows)
    head = f'<p class="seminote">{note}</p>' if note else ""
    return f'<h2>참고 — 타이머가 없는 반자동</h2>{head}{body}'


CRITERIA = """<ul class="guide">
<li><b>"반자동"과 자동은 다른 물건입니다.</b> 사료가 줄면 중력으로 채워지는 반자동(중력식)은
정해진 시간에 정량을 주지 못합니다. 출근 후 끼니를 챙기려는 목적이라면 맞지 않는데,
이름이 비슷해 헷갈리기 쉽습니다 — <b>실제로 토스쇼핑 자동급식기 판매 1위가 "회전형 반자동"</b>입니다.
상품명에 '반자동'이 있는지, 타이머·급여 횟수 설정이 되는지부터 보세요.</li>
<li><b>정전 대비</b> — 여기서 갈립니다. 어댑터 전용이면 코드가 빠지거나 정전됐을 때 급여가 멈춥니다. 하루 종일 집을 비운다면 배터리를 함께 쓰는 제품을 보세요. 판매 목록에는 거의 표기되지 않으니 상세페이지에서 직접 확인해야 합니다.</li>
<li><b>사료 알갱이 크기</b> — 제품마다 허용 범위가 있습니다. 이보다 작으면 배출 회전부에 끼고, 크면 통로에 걸립니다. 지금 주시는 사료를 자로 재보고 범위와 맞춰 보세요. 후기에서 가장 많이 터지는 문제입니다.</li>
<li><b>배출량 정확도</b> — 시간은 대체로 정확하지만 양은 제품마다 편차가 있습니다. 정량 급여가 필요한 아이라면 이 항목의 후기를 먼저 읽어보시는 게 좋습니다.</li>
<li><b>무게와 높이</b> — 가벼우면 힘센 아이가 밀거나 엎을 수 있습니다. 뚜껑이 쉽게 열리는 구조라면 과식 사고로 이어집니다.</li>
<li><b>세척</b> — 사료 통로에 기름과 가루가 낍니다. 분리해서 씻을 수 있는지가 반년 뒤 만족도를 가릅니다.</li>
<li><b>용량</b> — 클수록 좋은 게 아닙니다. 사료는 개봉하면 산패됩니다. 2~3주에 다 먹을 양이 적당합니다.</li>
</ul>"""

FAQ = [
    ("자동급식기, 정말 필요한가요?",
     "출퇴근이 불규칙하거나 집을 오래 비우는 날이 있다면 값을 합니다. 매일 같은 시간에 계신다면 굳이 필요하지 않습니다."),
    ("정전되면 사료가 안 나오나요?",
     "어댑터 전용 제품은 그렇습니다. 배터리를 함께 쓰는 제품은 정전 중에도 예약 급여가 유지됩니다. 다만 이 정보는 판매 목록에 잘 안 나오니 상세페이지에서 확인하셔야 합니다."),
    ("설정한 양이 정확히 나오나요?",
     "제품마다 다르고, 편차가 있다는 후기가 흔합니다. 사료 알갱이 크기가 제품 허용 범위를 벗어나면 특히 심해집니다. 정량이 중요하다면 구매 전 해당 항목의 후기를 꼭 읽어보세요."),
    ("습식 사료도 넣을 수 있나요?",
     "대부분 건사료 전용입니다. 습식은 통로에 들러붙고 상하기 때문에 습식 전용 급여기를 따로 찾으셔야 합니다."),
    ("쿠팡과 토스쇼핑 중 어디가 싼가요?",
     "같은 제품이 양쪽에 다 있는 경우가 드물어 단순 비교가 어렵습니다. 다만 적립률은 토스 7%, 쿠팡 5%로 일정했습니다. 표시가 차이가 2% 이내라면 적립까지 따져 토스가 유리합니다."),
]


def build_faq():
    return "\n".join(f'<div class="qa"><span class="q">{q}</span><span class="a">{a}</span></div>'
                     for q, a in FAQ)


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
        "intro": build_intro(d),
        "toppick": build_toppick(d, items),
        "blackout": build_blackout(items),
        "tldr": build_tldr(items),
        "table": build_table(items),
        "headtohead": build_headtohead(items),
        "table_note": build_table_note(d.get("platform_facts") or {}, items),
        "coupang_items": build_items(items, "coupang"),
        "toss_block": build_toss_block(items, d),
        "semi": build_semi(items, d.get("semi_note", "")),
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
    print(f'제목: {d.get("title", "")}')
    missing = [i["name"] for i in items if not (i.get("link") or "").strip()]
    if missing:
        print(f"\n제휴 링크 미입력 {len(missing)}개 → 버튼 비활성:")
        for m in missing:
            print("   -", m)


if __name__ == "__main__":
    main()
