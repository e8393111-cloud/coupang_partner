"""쿠팡 파트너스 Open API 클라이언트.

- HMAC-SHA256 서명 인증
- 상품 검색 / 베스트 카테고리 조회 (발굴)
- 딥링크(단축 제휴 링크) 생성

키가 없으면 mock 모드로 동작해 파이프라인을 그대로 시험할 수 있다.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .models import Product

_DOMAIN = "https://api-gateway.coupang.com"
_BASE = "/v2/providers/affiliate_open_api/apis/openapi"


def _signed_authorization(method: str, url_path: str, secret_key: str, access_key: str) -> str:
    """쿠팡 파트너스 CEA HMAC Authorization 헤더를 만든다.

    서명 메시지 = signed_date + METHOD + path + query(물음표 제외).
    signed_date 는 GMT 기준 yyMMdd'T'HHmmss'Z'.
    """
    path, _, query = url_path.partition("?")
    signed_date = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    message = signed_date + method + path + query
    signature = hmac.new(
        secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={access_key}, "
        f"signed-date={signed_date}, signature={signature}"
    )


class CoupangClient:
    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        timeout: int = 10,
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.timeout = timeout

    @property
    def is_mock(self) -> bool:
        return not (self.access_key and self.secret_key)

    # ------------------------------------------------------------------ #
    # 내부 요청 헬퍼
    # ------------------------------------------------------------------ #
    def _request(self, method: str, url_path: str, body: dict | None = None) -> dict[str, Any]:
        auth = _signed_authorization(method, url_path, self.secret_key, self.access_key)
        resp = requests.request(
            method,
            _DOMAIN + url_path,
            headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"},
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    # 상품 발굴
    # ------------------------------------------------------------------ #
    def search_products(self, keyword: str, limit: int = 10) -> list[Product]:
        """키워드로 상품을 검색한다."""
        if self.is_mock:
            return _mock_products(keyword, limit)

        query = urlencode({"keyword": keyword, "limit": limit})
        url_path = f"{_BASE}/v1/products/search?{query}"
        data = self._request("GET", url_path)
        items = (data.get("data") or {}).get("productData") or []
        return [Product.from_coupang(it) for it in items]

    def best_category_products(self, category_id: int, limit: int = 10) -> list[Product]:
        """카테고리별 베스트(잘 팔리는) 상품을 가져온다 — 발굴에 유용."""
        if self.is_mock:
            return _mock_products(f"베스트{category_id}", limit)

        query = urlencode({"limit": limit})
        url_path = f"{_BASE}/v1/products/bestcategories/{category_id}?{query}"
        data = self._request("GET", url_path)
        items = data.get("data") or []
        return [Product.from_coupang(it) for it in items]

    # ------------------------------------------------------------------ #
    # 딥링크 생성
    # ------------------------------------------------------------------ #
    def create_deeplink(self, urls: list[str], sub_id: str | None = None) -> dict[str, str]:
        """제품 URL → 단축 제휴 링크 매핑. sub_id 로 채널/게시물별 성과를 분리 추적한다."""
        if self.is_mock:
            return {u: _mock_deeplink(u, sub_id) for u in urls}

        body: dict[str, Any] = {"coupangUrls": urls}
        if sub_id:
            body["subId"] = sub_id
        url_path = f"{_BASE}/v1/deeplink"
        data = self._request("POST", url_path, body=body)
        result: dict[str, str] = {}
        for entry in data.get("data") or []:
            result[entry.get("originalUrl", "")] = entry.get("shortenUrl", "")
        return result


# ---------------------------------------------------------------------- #
# Mock 데이터 — 키 없이 파이프라인 검증용
# ---------------------------------------------------------------------- #
_MOCK_CATALOG = [
    ("바닥에 안 닿는 야전침대 텐트", 189000, "캠핑"),
    ("3초 완성 원터치 팝업 텐트", 89000, "캠핑"),
    ("무선 핸디 가습 선풍기", 32900, "생활가전"),
    ("각도조절 노트북 거치대", 24900, "사무용품"),
    ("초강력 차량용 무선 청소기", 59000, "자동차용품"),
]


def _mock_products(keyword: str, limit: int) -> list[Product]:
    out: list[Product] = []
    for i, (name, price, cat) in enumerate(_MOCK_CATALOG[:limit]):
        pid = f"mock-{abs(hash(keyword + name)) % 10_000_000}"
        out.append(
            Product(
                product_id=pid,
                name=name,
                price=price,
                image_url=f"https://example.com/img/{pid}.jpg",
                product_url=f"https://www.coupang.com/vp/products/{pid}",
                category_name=cat,
                is_rocket=True,
            )
        )
    return out


def _mock_deeplink(url: str, sub_id: str | None) -> str:
    token = abs(hash(url + (sub_id or ""))) % 100000
    return f"https://link.coupang.com/a/MOCK{token:05d}"
