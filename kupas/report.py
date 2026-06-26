"""쿠팡 파트너스 리포트 CSV 파서.

파트너스 대시보드에서 받은 실적 리포트(CSV)를 subId 기준으로 모아
{subId: {clicks, orders, revenue}} 로 돌려준다. 헤더 명칭은 변동이 잦아
한국어/영문 변형을 폭넓게 매칭한다.
"""

from __future__ import annotations

import csv
import re

# 헤더 후보 (소문자·공백제거 후 부분일치)
_SUBID_KEYS = ("subid", "서브아이디", "트래킹코드", "부가코드", "channel", "채널")
_CLICK_KEYS = ("click", "클릭")
_ORDER_KEYS = ("order", "주문", "결제건", "구매건")
_REV_KEYS = ("commission", "수수료", "적립", "수익", "정산", "revenue")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def _to_int(v: str) -> int:
    digits = re.sub(r"[^0-9]", "", v or "")
    return int(digits) if digits else 0


def _match(header: list[str], keys: tuple[str, ...]) -> str | None:
    for col in header:
        n = _norm(col)
        if any(k in n for k in keys):
            return col
    return None


def parse_coupang_report(path: str) -> dict[str, dict]:
    """리포트 CSV → {subId: {clicks, orders, revenue}} (subId별 합산)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        sub_col = _match(header, _SUBID_KEYS)
        click_col = _match(header, _CLICK_KEYS)
        order_col = _match(header, _ORDER_KEYS)
        rev_col = _match(header, _REV_KEYS)
        if sub_col is None:
            raise ValueError(
                f"subId 컬럼을 찾지 못했습니다. 헤더: {header}"
            )

        agg: dict[str, dict] = {}
        for row in reader:
            sub = (row.get(sub_col) or "").strip()
            if not sub:
                continue
            d = agg.setdefault(sub, {"clicks": 0, "orders": 0, "revenue": 0})
            if click_col:
                d["clicks"] += _to_int(row.get(click_col, ""))
            if order_col:
                d["orders"] += _to_int(row.get(order_col, ""))
            if rev_col:
                d["revenue"] += _to_int(row.get(rev_col, ""))
        return agg
