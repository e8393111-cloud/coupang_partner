"""mock 모드 기준 핵심 동작 스모크 테스트.

    python -m pytest        (pytest 설치 시)
    python tests/test_pipeline.py   (단독 실행)
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kupas.captions import CaptionGenerator
from kupas.config import Config
from kupas.coupang import CoupangClient, _signed_authorization
from kupas.models import Caption
from kupas.pipeline import DISCLOSURE, Pipeline


def _mock_config() -> Config:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Config(
        coupang_access_key=None,
        coupang_secret_key=None,
        anthropic_api_key=None,
        caption_model="claude-opus-4-8",
        subid_prefix="test",
        db_path=path,
    )


def test_hmac_signature_format():
    auth = _signed_authorization("GET", "/foo?bar=1", "secret", "access")
    assert auth.startswith("CEA algorithm=HmacSHA256")
    assert "access-key=access" in auth
    assert "signature=" in auth


def test_coupang_mock_search_and_deeplink():
    client = CoupangClient()
    assert client.is_mock
    products = client.search_products("캠핑", limit=3)
    assert len(products) == 3
    links = client.create_deeplink([products[0].product_url], sub_id="abc")
    assert products[0].product_url in links
    assert links[products[0].product_url].startswith("https://link.coupang.com/a/")


def test_caption_mock_generates_per_platform():
    gen = CaptionGenerator()
    assert gen.is_mock
    products = CoupangClient().search_products("청소기", limit=1)
    caps = gen.generate(products[0], platforms=("threads", "tiktok"))
    assert [c.platform for c in caps] == ["threads", "tiktok"]
    assert all(c.hook and c.body for c in caps)


def test_caption_render_includes_disclosure_and_link():
    cap = Caption(platform="threads", hook="후킹", body="본문", hashtags=["a", "b"])
    text = cap.render("https://link.coupang.com/a/X", DISCLOSURE)
    assert "후킹" in text and "본문" in text
    assert DISCLOSURE in text
    assert "https://link.coupang.com/a/X" in text
    assert "#a" in text and "#b" in text


def test_pipeline_run_and_persist():
    pipe = Pipeline(_mock_config())
    pieces = pipe.run(keyword="텐트", limit=2)
    assert len(pieces) == 2
    assert all(p.deeplink for p in pieces)

    content = pipe.storage.list_content()
    assert len(content) == 2
    posts = pipe.storage.list_posts(content[0]["id"])
    assert len(posts) == 2  # threads + tiktok

    pipe.storage.record_performance(posts[0]["id"], clicks=10, orders=1, revenue=5000)
    summary = pipe.storage.summary()
    assert summary["clicks"] == 10
    assert summary["revenue"] == 5000


def test_pipeline_requires_keyword_or_category():
    pipe = Pipeline(_mock_config())
    try:
        pipe.run()
    except ValueError:
        pass
    else:
        raise AssertionError("keyword/category 없이 ValueError 가 나야 함")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}개 통과")
