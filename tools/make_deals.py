#!/usr/bin/env python3
"""하루특가「오늘의 특가」페이지 생성기.

    python3 tools/make_deals.py deals_data/today.json
    python3 tools/make_deals.py deals_data/today.json --weekly   # 주간 아카이브 글

설계 근거 (blog/deals_plan.md)
- 특가는 `endAt` 이 지나면 값이 0이다. **날짜별 글을 쌓지 않고 한 페이지를 갱신**한다.
- 신선도가 이 페이지의 유일한 자산이므로 **마지막 갱신 시각을 크게** 박는다.
- **0건인 날이 정상이다.** 편성이 없으면 그렇게 쓴다 — 지난 특가 재탕은 금지.
- 링크는 반드시 쉐어링크 발급분(`shortUrl`). `productUrl` 은 수익이 0원이다.
"""
import argparse
import html
import json
import os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KST = timezone(timedelta(hours=9))


def esc(v):
    return html.escape(str(v), quote=True)


def won(v):
    return f"{int(v):,}원" if isinstance(v, (int, float)) and v else "—"


def remaining(end_at, now):
    """만료 판정용. 표시에는 쓰지 않는다 — end_label 을 쓴다."""
    try:
        end = datetime.fromisoformat(end_at)
    except (TypeError, ValueError):
        return ""
    return "종료" if (end - now).total_seconds() <= 0 else "진행"


def end_label(end_at, now):
    """종료 시각을 절대값으로 적는다.

    「3시간 남음」은 페이지가 낡는 순간 거짓이 된다. 그걸 막으려면 자주 갱신하거나
    브라우저에서 계산해야 하는데, 토스가 CIDR 을 지원하지 않아 자주 갱신할 수 없고
    (클라우드 세션은 출발지 IP 가 고정되지 않는다), 블로그스팟 악성코드 단속 때문에
    인라인 스크립트도 기본으로 안 넣는다.

    「오늘 23:59까지」는 늙지 않는다. 며칠 뒤에 봐도 참인 문장이고, 보는 사람이
    지금 시계와 비교해 판단할 수 있다. 제약이 오히려 정직한 표기를 강제한 경우다.
    """
    try:
        end = datetime.fromisoformat(end_at)
    except (TypeError, ValueError):
        return ""
    d = (end.date() - now.date()).days
    day = "오늘" if d == 0 else "내일" if d == 1 else f"{end.month}월 {end.day}일"
    return f'{day} {end.strftime("%H:%M")}까지'


CSS = """
.dl{--ink:#12291f;--body:#3a4642;--mut:#6f807a;--brand:#1a6b4a;--wash:#f1f7f3;
 --hot:#c0392b;--hot-wash:#fdf0ee;--rule:#e4efe9;
 font-family:'Pretendard',-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
 color:var(--body);font-size:16px;line-height:1.7;word-break:keep-all;letter-spacing:-0.011em}
.dl *{box-sizing:border-box}
.dl b{font-weight:600;color:var(--ink)}
.dl .disc{font-size:12.5px;line-height:1.6;color:var(--brand);background:var(--wash);
 border-left:3px solid var(--brand);padding:11px 14px;margin:0 0 18px}
.dl .stamp{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
 border-bottom:2px solid var(--brand);padding-bottom:10px;margin:0 0 6px}
.dl .stamp b{font-size:20px;color:var(--brand)}
.dl .stamp span{font-size:13px;color:var(--mut)}
.dl .note{font-size:13.5px;color:var(--mut);margin:0 0 24px}
.dl .empty{background:var(--wash);border-left:3px solid var(--brand);padding:22px;
 font-size:16px;line-height:1.75}
.dl .row{display:flex;gap:14px;padding:16px 0;border-bottom:1px solid var(--rule)}
.dl .row:first-of-type{border-top:2px solid var(--brand)}
.dl .th{flex:0 0 96px}
.dl .th img{width:96px;height:96px;object-fit:cover;border-radius:3px;background:var(--wash)}
.dl .bd{flex:1 1 auto;min-width:0}
.dl .nm{font-size:15.5px;font-weight:600;color:var(--ink);line-height:1.45;margin:0 0 6px}
.dl .pr{font-size:21px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
.dl .pr s{font-size:13.5px;font-weight:400;color:var(--mut);margin-left:8px}
.dl .rate{color:var(--hot);font-weight:700;margin-right:7px}
.dl .meta{font-size:13px;color:var(--mut);margin:5px 0 0}
.dl .left{display:inline-block;background:var(--hot-wash);color:var(--hot);
 font-size:12.5px;font-weight:700;padding:2px 8px;border-radius:2px;margin-top:7px}
.dl .buy{display:inline-block;margin-top:9px;padding:8px 16px;font-size:14px;font-weight:700;
 color:#1b64da;border:1.5px solid #1b64da;border-radius:2px;text-decoration:none}
.dl .buy:hover{background:#1b64da;color:#fff}
.dl .foot{margin-top:34px;padding-top:16px;border-top:2px solid var(--brand);
 color:var(--mut);font-size:12.5px;line-height:1.7}
@media (max-width:600px){.dl .th{flex:0 0 72px}.dl .th img{width:72px;height:72px}}
"""

DISCLOSURE = "이 페이지는 토스쇼핑 쉐어링크 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

# 만료 판정을 방문자 브라우저로 옮긴다.
#
# 남은 시간을 생성 시점에 계산해 박아두면 페이지가 낡는 순간 거짓말이 된다.
# 끝난 특가를 눌러 특가 아닌 가격을 보는 게 이 페이지가 신뢰를 잃는 유일한 방식이고,
# 그걸 막으려고 하루 네 번 갱신이 필요했다. 종료 시각만 심어두고 화면에서 계산하면
# 며칠 낡아도 틀리지 않는다 — 갱신은 "거짓말 방지"가 아니라 "새 특가 반영"이 된다.
#
# 블로거 편집기를 통과해야 하므로 < 와 & 를 쓰지 않는다 (HTML 로 오인돼 깨진다).
#
# ⚠️ 기본값은 꺼짐(--countdown 으로만 켠다). 2026-08-04~05 구글이 블로그스팟에
# 「악성코드 및 유사 악성 콘텐츠」 정책으로 일괄 단속을 돌렸고 오탐이 대거 나왔다.
# 배경은 VEIL#DROP — 블로그스팟이 암호화 페이로드 배포처로 악용된 사건이다.
# 그 스위프 한가운데서 개설 직후 블로그가 제휴 리다이렉트 + 인라인 스크립트를
# 달고 있는 건 위험한 조합이다. 기능의 값어치보다 블로그를 잃는 손실이 크다.
# 판이 가라앉으면 켜거나, 예약 실행으로 페이지를 자주 다시 생성해 대체한다.
JS = """<script>
(function(){
  var root = document.querySelector('.dl');
  if (!root) { return; }
  function tick(){
    var rows = root.querySelectorAll('.row[data-end]');
    var alive = 0;
    rows.forEach(function(row){
      var raw = row.getAttribute('data-end');
      if (raw.indexOf('+') === -1) { if (raw.indexOf('Z') === -1) { raw = raw + '+09:00'; } }
      var end = Date.parse(raw);
      if (isNaN(end)) { alive = alive + 1; return; }
      var sec = Math.floor((end - Date.now()) / 1000);
      if (sec > 0) {
        alive = alive + 1;
        var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
        var el = row.querySelector('.left');
        if (el) { el.textContent = h ? (h + '시간 ' + m + '분 남음') : (m + '분 남음'); }
      } else {
        row.hidden = true;
      }
    });
    var gone = root.querySelector('#dl-gone');
    if (gone) { gone.hidden = (alive > 0); }
  }
  tick();
  setInterval(tick, 30000);
})();
</script>"""


def render_row(it, now):
    if remaining(it.get("endAt"), now) == "종료":
        return ""   # 만료분은 생성 시점에 걸러낸다 (문서 경고 사항)
    left = end_label(it.get("endAt"), now)
    th = (f'<div class="th"><img src="{esc(it["thumbnailUrl"])}" alt="" loading="lazy"></div>'
          if it.get("thumbnailUrl") else "")
    rate = f'<span class="rate">{it["discountRate"]}%</span>' if it.get("discountRate") else ""
    orig = f'<s>{won(it.get("originalPrice"))}</s>' if it.get("originalPrice") else ""
    # 평점은 없고 후기 수만 있는 경우가 있다. 있는 것만 적는다.
    score = f'★{it["reviewScore"]} · ' if it.get("reviewScore") else ""
    rv = (f'{score}후기 {int(it["reviewCount"]):,}건'
          if it.get("reviewCount") else "후기 없음")
    # 수익은 발급받은 쉐어링크로만 집계된다. productUrl 은 추적이 안 된다.
    url = it.get("shareUrl") or ""
    btn = (f'<a class="buy" href="{esc(url)}" target="_blank" rel="noopener nofollow sponsored">'
           f'토스쇼핑에서 보기</a>' if url else
           '<span class="meta">링크 준비 중</span>')
    # 종료 시각을 심어두면 브라우저가 만료를 판정한다 → 페이지가 낡아도 거짓말을
    # 하지 않는다. 갱신 주기가 "거짓말 방지"가 아니라 "새 특가 반영"의 문제가 된다.
    end = f' data-end="{esc(it["endAt"])}"' if it.get("endAt") else ""
    return (f'<div class="row"{end}>{th}<div class="bd">'
            f'<p class="nm">{esc(it.get("displayName", ""))}</p>'
            f'<div class="pr">{rate}{won(it.get("displayPrice"))}{orig}</div>'
            f'<p class="meta">{rv}</p>'
            f'<div class="left">{left}</div><br>{btn}</div></div>')


def build(data, weekly=False, countdown=False):
    now = datetime.now(KST)
    items = [i for i in data.get("items", []) if not i.get("isSoldOut")]
    rows = "".join(render_row(i, now) for i in items)

    if weekly:
        head = (f'<div class="stamp"><b>이번 주 가장 쌌던 것</b>'
                f'<span>{data.get("week_label", now.strftime("%Y년 %m월 %W주"))}</span></div>'
                f'<p class="note">그 주 하루특가 중 할인율이 가장 컸던 상품입니다. '
                f'<b>특가는 이미 끝났습니다.</b> 지금 가격은 다를 수 있고, '
                f'이 기록은 "이 정도면 싸다"는 기준선으로만 봐주세요.</p>')
    elif data.get("source") == "api":
        head = (f'<div class="stamp"><b>오늘의 특가</b>'
                f'<span>{now.strftime("%m월 %d일 %H:%M")} 확인</span></div>'
                f'<p class="note">토스쇼핑 하루특가입니다. <b>종료 시각이 지나면 원래 가격으로 돌아갑니다.</b> '
                f'각 상품에 끝나는 시각을 적어 뒀습니다.</p>')
    else:
        # 갱신 시각을 찍지 않는다. 갱신한 적이 없기 때문이다.
        head = ('<div class="stamp"><b>오늘의 특가</b><span>준비 중</span></div>'
                '<p class="note">토스쇼핑 하루특가를 정리하는 자리입니다. '
                '<b>종료 시각이 지나면 원래 가격으로 돌아갑니다.</b> '
                '각 상품에 끝나는 시각을 적습니다.</p>')

    if rows:
        # 전부 만료되면 브라우저가 이 블록을 대신 보여준다. 카운트다운이 꺼져 있으면
        # 아무도 이걸 열지 않으므로 아예 내보내지 않는다 (죽은 마크업 금지).
        gone = ('<div class="empty" id="dl-gone" hidden>'
                '<b>지금은 진행 중인 특가가 없습니다.</b><br>'
                '올려둔 특가가 모두 종료됐습니다. 끝난 가격을 그대로 두면 눌렀을 때 '
                '특가가 아닌 값이 나오기 때문에 화면에서 내렸습니다.</div>'
                ) if countdown and not weekly else ""
        body = rows + gone
    elif data.get("source") == "api":
        # 편성이 없는 날이 정상이다. 지난 특가를 재탕하지 않는다.
        body = ('<div class="empty">오늘은 <b>편성된 하루특가가 없습니다.</b><br>'
                '지난 특가를 그대로 두면 눌렀을 때 특가가 아닌 가격이 나오기 때문에, '
                '없는 날은 없다고 적습니다. 다음 갱신 때 다시 확인해 주세요.</div>')
    else:
        # 0건이라고 "편성이 없다"고 쓰면 안 된다. 확인을 못 한 것과 확인해서
        # 없는 것은 다른 상태다. 전자를 후자처럼 쓰면 그게 거짓말이다.
        body = ('<div class="empty"><b>준비 중입니다.</b><br>'
                '토스쇼핑 하루특가를 이 자리에 정리합니다. '
                '연동이 끝나는 대로 시작합니다.</div>')

    stamp = (f'<br>마지막 확인 {now.strftime("%Y-%m-%d %H:%M")} KST'
             if data.get("source") == "api" else "")
    if rows and not countdown:
        # 목록은 생성 시점에 걸러진다. 그 이후 끝난 건 남아 있을 수 있으므로,
        # 각 상품의 종료 시각과 지금 시각을 비교하면 된다고 알려준다.
        stamp += ('<br>갱신 사이에 종료된 상품이 남아 있을 수 있습니다. '
                  '<b>각 상품의 종료 시각</b>을 지금 시각과 비교해 주세요.')
    return (f'<style>{CSS}</style>\n<div class="dl">\n'
            f'<p class="disc">{DISCLOSURE}</p>\n{head}\n{body}\n'
            f'<div class="foot">가격·재고는 표기 시각 기준이며 판매처 사정으로 바뀔 수 있습니다. '
            f'구매 전 상품 페이지에서 다시 확인해 주세요.{stamp}</div>\n'
            + (JS if rows and countdown and not weekly else "") + '</div>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--countdown", action="store_true",
                    help="만료 카운트다운 스크립트를 넣는다. 기본은 꺼짐 — "
                         "블로그스팟 악성코드 오탐 단속(2026-08) 때문에 명시적으로만 켠다")
    ap.add_argument("--out")
    a = ap.parse_args()

    p = a.data if os.path.isabs(a.data) else os.path.join(ROOT, a.data)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    out_html = build(data, a.weekly, a.countdown)
    out = a.out or os.path.join("blog", "deals",
                                "weekly.html" if a.weekly else "today.html")
    out = out if os.path.isabs(out) else os.path.join(ROOT, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(out_html)

    # 렌더와 같은 기준으로 센다. 품절만 걸러내면 이미 끝난 특가까지 "노출"로
    # 잡혀서, 화면에 2건인데 3건이라고 보고하게 된다.
    now = datetime.now(KST)
    live = [i for i in data.get("items", [])
            if not i.get("isSoldOut") and remaining(i.get("endAt"), now) != "종료"]
    nolink = [i for i in live if not i.get("shareUrl")]
    print(f'생성: {os.path.relpath(out, ROOT)} ({len(out_html):,}자) · 노출 {len(live)}건')
    if nolink:
        print(f'⚠ 쉐어링크 미발급 {len(nolink)}건 → 수익이 집계되지 않습니다')
        for i in nolink[:5]:
            print(f'   - {i.get("displayName", "")[:40]} (tacaItemId {i.get("tacaItemId")})')


if __name__ == "__main__":
    main()
