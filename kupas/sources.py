"""멀티 소스 추상화 — 국내(쿠팡)와 글로벌(Amazon/AliExpress)을 갈아끼운다.

각 마켓은 소스 플랫폼·언어·통화를 정의하고, `SourceProvider` 는 발굴 에이전트와
게시 에이전트가 쓰는 최소 인터페이스(상품검색·베스트·딥링크)를 제공한다.
실제 API 키가 없으면 mock 으로 동작해 국내+글로벌 동시 흐름을 그대로 검증할 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .coupang import CoupangClient
from .models import Product


@dataclass(frozen=True)
class Market:
    key: str          # "kr" | "global" | "ali"
    label: str        # 표시용
    language: str     # "ko" | "en"
    currency: str     # "KRW" | "USD"
    platform: str     # "coupang" | "amazon" | "aliexpress"


MARKETS: dict[str, Market] = {
    "kr": Market("kr", "국내", "ko", "KRW", "coupang"),
    "global": Market("global", "글로벌(Amazon)", "en", "USD", "amazon"),
    "ali": Market("ali", "글로벌(AliExpress)", "en", "USD", "aliexpress"),
}

DEFAULT_MULTI = ("kr", "global")  # --market all 시 실행할 마켓


@runtime_checkable
class SourceProvider(Protocol):
    market: Market
    is_mock: bool

    def search_products(self, keyword: str, limit: int) -> list[Product]: ...
    def best_category_products(self, category_id: int, limit: int) -> list[Product]: ...
    def create_deeplink(self, urls: list[str], sub_id: str | None = None) -> dict[str, str]: ...


class CoupangSource:
    """국내 — 기존 CoupangClient 래핑."""

    def __init__(self, market: Market, client: CoupangClient) -> None:
        self.market = market
        self.client = client

    @property
    def is_mock(self) -> bool:
        return self.client.is_mock

    def search_products(self, keyword: str, limit: int) -> list[Product]:
        return self.client.search_products(keyword, limit)

    def best_category_products(self, category_id: int, limit: int) -> list[Product]:
        return self.client.best_category_products(category_id, limit)

    def create_deeplink(self, urls: list[str], sub_id: str | None = None) -> dict[str, str]:
        return self.client.create_deeplink(urls, sub_id=sub_id)


class _MockGlobalSource:
    """글로벌 공통 mock 소스 (Amazon/AliExpress). 실 API 는 추후 연결."""

    _CATALOG = [
        ("Cordless Neck & Shoulder Massager", 45, "Health"),
        ("Anti-Fatigue Kitchen Standing Mat", 39, "Kitchen"),
        ("Adjustable Ergonomic Reading Pillow", 34, "Home"),
        ("Cordless Handheld Vacuum for Car", 52, "Auto"),
        ("Raised Garden Bed Planter Kit", 68, "Garden"),
        ("No-Bend Pet Water Fountain", 33, "Pet"),
    ]

    def __init__(self, market: Market, short_host: str) -> None:
        self.market = market
        self.short_host = short_host

    is_mock = True

    def search_products(self, keyword: str, limit: int) -> list[Product]:
        out: list[Product] = []
        for name, price, cat in self._CATALOG[:limit]:
            pid = f"{self.market.platform[:3]}-{abs(hash(keyword + name)) % 10_000_000}"
            out.append(Product(
                product_id=pid,
                name=name,
                price=price,
                image_url=f"https://example.com/img/{pid}.jpg",
                product_url=f"https://{self.market.platform}.com/dp/{pid}",
                category_name=cat,
                is_rocket=True,  # 빠른배송/프라임 상당
            ))
        return out

    def best_category_products(self, category_id: int, limit: int) -> list[Product]:
        return self.search_products(f"best{category_id}", limit)

    def create_deeplink(self, urls: list[str], sub_id: str | None = None) -> dict[str, str]:
        result = {}
        for u in urls:
            token = abs(hash(u + (sub_id or ""))) % 100000
            result[u] = f"https://{self.short_host}/MOCK{token:05d}"
        return result


def get_source(market_key: str, config) -> SourceProvider:
    """마켓 키 → 소스 프로바이더. 키 없으면 mock."""
    if market_key not in MARKETS:
        raise ValueError(f"알 수 없는 마켓: {market_key} (가능: {list(MARKETS)})")
    m = MARKETS[market_key]
    if m.platform == "coupang":
        return CoupangSource(m, CoupangClient(config.coupang_access_key, config.coupang_secret_key))
    if m.platform == "amazon":
        return _MockGlobalSource(m, "amzn.to")
    if m.platform == "aliexpress":
        return _MockGlobalSource(m, "s.click.aliexpress.com/e")
    raise ValueError(f"지원하지 않는 플랫폼: {m.platform}")


def resolve_markets(market_arg: str) -> list[str]:
    """--market 인자 → 실행할 마켓 키 목록. 'all' 은 국내+글로벌."""
    if market_arg == "all":
        return list(DEFAULT_MULTI)
    return [market_arg]
