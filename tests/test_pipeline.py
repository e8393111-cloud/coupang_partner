"""mock 모드 기준 스모크 테스트 — 에이전트별 단위 + 오케스트레이터 통합.

    python -m pytest        (pytest 설치 시)
    python tests/test_pipeline.py   (단독 실행)
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kupas.agents.base import AgentLog, Brief
from kupas.agents.curation import CurationAgent, _commission_score, _price_score
from kupas.agents.discovery import DiscoveryAgent
from kupas.agents.orchestrator import Orchestrator
from kupas.agents.publish import DISCLOSURE, PublishAgent, make_subid
from kupas.captions import CaptionGenerator
from kupas.config import Config
from kupas.coupang import CoupangClient, _signed_authorization
from kupas.models import Caption, Product


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


def _product(price: int, rocket: bool = True, cat: str = "캠핑", name: str = "테스트") -> Product:
    return Product(
        product_id=f"p{price}{int(rocket)}",
        name=name,
        price=price,
        image_url="",
        product_url=f"https://www.coupang.com/vp/products/{price}",
        category_name=cat,
        is_rocket=rocket,
    )


# ── 인프라 ──────────────────────────────────────────────────────────
def test_hmac_signature_format():
    auth = _signed_authorization("GET", "/foo?bar=1", "secret", "access")
    assert auth.startswith("CEA algorithm=HmacSHA256")
    assert "access-key=access" in auth and "signature=" in auth


def test_coupang_mock_search_and_deeplink():
    client = CoupangClient()
    assert client.is_mock
    products = client.search_products("캠핑", limit=3)
    assert len(products) == 3
    links = client.create_deeplink([products[0].product_url], sub_id="abc")
    assert links[products[0].product_url].startswith("https://link.coupang.com/a/")


# ── 발굴 에이전트 ───────────────────────────────────────────────────
def test_discovery_agent_keyword_and_category():
    agent = DiscoveryAgent(CoupangClient())
    brief = Brief(keyword="텐트", shortlist_size=5)
    products = agent.run(brief, AgentLog("discovery"))
    assert 1 <= len(products) <= 5

    cat_products = agent.run(Brief(category_id=1016, shortlist_size=4), AgentLog("d"))
    assert len(cat_products) >= 1


def test_discovery_requires_keyword_or_category():
    agent = DiscoveryAgent(CoupangClient())
    try:
        agent.run(Brief(), AgentLog("d"))
    except ValueError:
        pass
    else:
        raise AssertionError("keyword/category 없이 ValueError 가 나야 함")


# ── 선별 에이전트 (점수 엔진) ───────────────────────────────────────
def test_commission_score_increases_with_price():
    low, _ = _commission_score(_product(10_000))
    high, _ = _commission_score(_product(200_000))
    assert high > low


def test_price_score_peaks_at_sweet_spot():
    mid, _ = _price_score(_product(50_000))
    far, _ = _price_score(_product(2_000_000))
    assert mid > far


def test_rocket_outranks_non_rocket_all_else_equal():
    agent = CurationAgent()
    rocket = agent._heuristic(_product(50_000, rocket=True))
    plain = agent._heuristic(_product(50_000, rocket=False))
    assert rocket.total > plain.total


def test_curation_ranks_and_cuts_to_target():
    agent = CurationAgent()
    products = [_product(p) for p in (5_000, 50_000, 1_500_000, 60_000)]
    brief = Brief(target_count=2, shortlist_size=10)
    scored = agent.run(brief, products, AgentLog("curation"))
    assert len(scored) == 2  # target_count 컷
    totals = [s.score.total for s in scored]
    assert totals == sorted(totals, reverse=True)  # 내림차순 정렬
    # sweet-spot 가격대가 극단가보다 위
    assert scored[0].product.price not in (5_000, 1_500_000)


# ── 게시 에이전트 ───────────────────────────────────────────────────
def test_subid_is_alphanumeric_and_platform_scoped():
    p = _product(50_000)
    tt = make_subid("test-채널", "tiktok", p)
    th = make_subid("test-채널", "threads", p)
    assert tt.isalnum() and th.isalnum()
    assert tt != th  # 플랫폼별로 분리


def test_caption_render_includes_disclosure_and_link():
    cap = Caption(platform="threads", hook="후킹", body="본문", hashtags=["a", "b"])
    text = cap.render("https://link.coupang.com/a/X", DISCLOSURE)
    assert "후킹" in text and "본문" in text and DISCLOSURE in text
    assert "https://link.coupang.com/a/X" in text and "#a" in text


# ── 오케스트레이터 통합 ─────────────────────────────────────────────
def test_orchestrator_full_chain_and_persist():
    orch = Orchestrator(_mock_config())
    result = orch.run(Brief(keyword="텐트", target_count=2, shortlist_size=10))
    assert len(result.pieces) == 2
    assert all(p.deeplink and p.score is not None for p in result.pieces)
    # 4개 에이전트 로그가 모두 남는다
    agents_logged = {log.agent for log in result.logs}
    assert {"discovery", "curation", "copy", "publish"} <= agents_logged

    content = orch.storage.list_content()
    assert len(content) == 2
    assert content[0]["score"] is not None  # 점수 저장됨
    posts = orch.storage.list_posts(content[0]["id"])
    assert len(posts) == 2  # threads + tiktok


def test_orchestrator_curate_only_skips_captions():
    orch = Orchestrator(_mock_config())
    result = orch.curate(Brief(keyword="청소기", target_count=3, shortlist_size=10))
    assert 1 <= len(result.shortlist) <= 3
    assert result.pieces == []  # 카피·게시는 생략


def test_caption_generator_mock_per_platform():
    gen = CaptionGenerator()
    assert gen.is_mock
    products = CoupangClient().search_products("청소기", limit=1)
    caps = gen.generate(products[0], platforms=("threads", "tiktok"))
    assert [c.platform for c in caps] == ["threads", "tiktok"]
    assert all(c.hook and c.body for c in caps)


# ── 카피 강화 (few-shot / 대체 후킹) ────────────────────────────────
def test_fewshot_block_is_platform_specific():
    from kupas.exemplars import fewshot_block

    tt = fewshot_block("tiktok")
    assert "잘 터진 예시" in tt and "hook:" in tt


def test_media_agent_builds_brief_from_caption():
    from kupas.agents.media import MediaAgent
    from kupas.models import Caption, ScoredProduct
    from kupas.agents.curation import CurationAgent

    product = _product(50_000, name="신박 청소기")
    scored = ScoredProduct(product, CurationAgent()._heuristic(product))
    cap = Caption(platform="tiktok", hook="이거 5초컷", body="흡입력 실화", hashtags=["청소"])
    briefs = MediaAgent().run(Brief(), scored, [cap], AgentLog("media"))
    assert len(briefs) == 1
    mb = briefs[0]
    assert mb.platform == "tiktok" and mb.shots and mb.video_prompt
    assert mb.shots[0].overlay == cap.hook  # 첫 컷이 후킹


def test_orchestrator_with_media_attaches_briefs():
    orch = Orchestrator(_mock_config())
    result = orch.run(Brief(keyword="청소기", target_count=1, with_media=True))
    piece = result.pieces[0]
    assert len(piece.media) == len(piece.captions)
    assert all(m.shots for m in piece.media)


def test_mock_caption_has_alt_hooks_and_varies():
    gen = CaptionGenerator()
    a = gen.generate(_product(50_000, name="A상품", cat="캠핑"))[0]
    b = gen.generate(_product(90_000, name="B상품", cat="주방용품"))[0]
    assert len(a.alt_hooks) == 2 and len(b.alt_hooks) == 2
    # 서로 다른 상품이면 후킹도 달라야(아키타입 분산)
    assert a.hook != b.hook


# ── 게시 에이전트 확장 (큐·예약·리포트 수집) ──────────────────────
def test_per_platform_links_and_rendered():
    orch = Orchestrator(_mock_config())
    piece = orch.run(Brief(keyword="텐트", target_count=1)).pieces[0]
    assert set(piece.platform_subids) == {"threads", "tiktok"}
    assert piece.platform_subids["threads"] != piece.platform_subids["tiktok"]
    assert all(DISCLOSURE in piece.rendered[p] for p in piece.platform_subids)
    # 각 플랫폼 게시본문엔 자기 플랫폼 링크만 들어가야(귀속 안 깨짐)
    assert piece.platform_links["tiktok"] in piece.rendered["tiktok"]
    assert piece.platform_links["threads"] not in piece.rendered["tiktok"]


def test_subid_unique_across_reposts():
    orch = Orchestrator(_mock_config())
    p1 = orch.run(Brief(keyword="텐트", target_count=1)).pieces[0]
    p2 = orch.run(Brief(keyword="텐트", target_count=1)).pieces[0]
    # 같은 상품을 다시 올려도 게시물 고유 토큰으로 subId 가 겹치지 않는다
    if p1.product.product_id == p2.product.product_id:
        assert p1.platform_subids["tiktok"] != p2.platform_subids["tiktok"]
    # 리포트 import 는 정확히 한 행만 갱신(이중 집계 방지)
    sub = p1.platform_subids["tiktok"]
    assert orch.storage.import_report({sub: {"clicks": 10, "orders": 0, "revenue": 0}}) == 1


def test_queue_and_schedule():
    orch = Orchestrator(_mock_config())
    orch.run(Brief(keyword="텐트", target_count=1))
    queue = orch.storage.export_queue()
    assert len(queue) == 2 and all(q["caption"] and q["deeplink"] for q in queue)
    # 미래 예약은 큐(현재 due)에서 빠진다
    orch.storage.schedule_post(queue[0]["post_id"], "2999-01-01 00:00")
    assert len(orch.storage.export_queue()) == 1


def test_import_report_matches_by_subid():
    orch = Orchestrator(_mock_config())
    piece = orch.run(Brief(keyword="텐트", target_count=1)).pieces[0]
    tiktok_sub = piece.platform_subids["tiktok"]
    updated = orch.storage.import_report({tiktok_sub: {"clicks": 200, "orders": 5, "revenue": 17500}})
    assert updated == 1  # 틱톡 post 1건만 매칭
    s = orch.storage.summary()
    assert s["clicks"] == 200 and s["revenue"] == 17500


def test_report_parser_handles_korean_headers():
    import tempfile
    from kupas.report import parse_coupang_report

    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
        f.write("서브아이디,클릭수,주문건수,수수료\n")
        f.write("kupastiktokP1,120,3,\"12,500\"\n")
        f.write("kupastiktokP1,30,1,4000\n")  # 같은 subId 합산
    report = parse_coupang_report(path)
    os.remove(path)
    assert report["kupastiktokP1"]["clicks"] == 150
    assert report["kupastiktokP1"]["orders"] == 4
    assert report["kupastiktokP1"]["revenue"] == 16500


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}개 통과")
