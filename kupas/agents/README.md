# kupas 에이전트

각 분야가 독립 에이전트(역할 + `run(입력)→출력` 모듈)로 동작하고, `Orchestrator` 가
Brief 를 흘려보내며 조율한다. 자율 도구루프는 쓰지 않고, **지능이 필요한 곳에서만**
Claude 를 역할별 프롬프트로 호출한다. 모든 에이전트는 **mock 폴백**을 갖는다
(키 없이 전체 사슬 동작).

```
Brief ─▶ ① Discovery ▶ ② Curation ▶ ③ Copy ▶ ④ Media(선택) ▶ ⑤ Publish ─▶ ContentPiece
              발굴          선별★         카피        소재 기획         게시 준비
```

공통 규약(`base.py`):

| 구성요소 | 설명 |
|----------|------|
| `Brief` | 작업 지시서. 키워드/카테고리·플랫폼·목표개수·마켓(kr/global/ali)·언어·통화·타깃(audience) |
| `Agent` | `name`·`role`·`run(...)` 프로토콜 |
| `AgentLog` | 각 에이전트가 "왜 이렇게 했는지" 남기는 근거 로그 (CLI 가 출력) |

---

## ① DiscoveryAgent — `discovery.py`

**역할**: 트렌드 후보 발굴가. 마켓 소스에서 상품 후보를 모은다.

| | |
|--|--|
| 입력 | `Brief`, `SourceProvider`(오케스트레이터가 주입), `AgentLog` |
| 출력 | `list[Product]` (최대 `shortlist_size`) |
| Claude | 선택 — 시드 키워드를 연관 키워드 3~4개로 확장(`_expand`). 실패 시 원 키워드로 계속 |

동작: `category_id` 가 있으면 베스트 카테고리 조회, 아니면 키워드(확장 포함) 검색.
여러 키워드로 나눠 조회할 때 **올림 나눗셈**으로 부족분(under-fetch)을 방지하고,
`product_id` 로 중복 제거한다.

주의: 소스를 직접 만들지 않는다 — 어떤 마켓(쿠팡/Amazon/AliExpress)이냐는
`sources.get_source()` 를 거쳐 주입받는다.

---

## ② CurationAgent — `curation.py` ★핵심

**역할**: 상품 큐레이터. "터질 상품"만 골라 다음 단계 비용(카피 토큰·영상 크레딧)을
아낀다.

| | |
|--|--|
| 입력 | `Brief`, `list[Product]`, `AgentLog` |
| 출력 | `list[ScoredProduct]` (점수 내림차순, `target_count` 로 컷) |
| Claude | 선택 — 2단계 신박도(vision) 점수. `brief.use_vision` 일 때만 |

2단계 깔때기:

1. **휴리스틱 (전수, 무료)** — API 필드만으로:
   - 수수료 기대값: `price × 카테고리 수수료율` (`CATEGORY_COMMISSION`, 기본 3%)
   - 가격대 적합도: **통화별 sweet-spot 가우시안** (KRW ~5만 / USD ~$40)
   - 로켓/프라임 보너스
   - `audience == "40+"` 면 건강·홈·주방·정원·반려 카테고리 **+40 가점**
2. **신박도 (shortlist 만, 선택)** — 상품명+이미지를 Claude vision 이 보고
   "이게 된다고?" 호기심 유발도 0~100. mock 일 땐 휴리스틱 대체값.

튜닝 포인트: `ScoreWeights`(가중치), `CATEGORY_COMMISSION`(실 정산율에 맞게 조정),
`SWEET_SPOT`/`SIGMA`(통화별), `AUDIENCE_40_CATS`.

---

## ③ CopyAgent — `copy.py` (엔진: `../captions.py`)

**역할**: 숏폼 카피라이터. 스크롤을 멈추는 후킹 카피를 플랫폼·언어별로 쓴다.

| | |
|--|--|
| 입력 | `Brief`, `ScoredProduct`, `AgentLog` |
| 출력 | `list[Caption]` (hook / body / hashtags / **alt_hooks 2개**) |
| Claude | **필수** (구조화 출력). 키 없으면 아키타입 기반 mock |

- **few-shot**: 실제 터진 게시물의 첫 줄 구조(`exemplars.py` 아키타입 — 한국어 6종,
  영어 6종)를 프롬프트에 주입. "구조만 참고, 문장은 새로"가 규칙.
- **이중언어**: `brief.language`(ko/en)에 따라 시스템 프롬프트·few-shot·가격 표기가
  바뀐다. 영어는 40+ 톤(혜택 중심·명확) 기본.
- **대체 후킹 2개**(서로 다른 심리 트리거) — A/B 테스트용.
- 광고 고지·링크는 본문에 넣지 않는다(Publish 가 렌더 시 붙임).

---

## ④ MediaAgent — `media.py` (선택 단계)

**역할**: 숏폼 PD. 카피를 살리는 소재 기획서를 만든다. **실제 영상 생성은 하지
않는다** — 그 직전(무엇을 어떻게 찍을지/생성할지)까지가 책임.

| | |
|--|--|
| 입력 | `Brief`, `ScoredProduct`, `list[Caption]`, `AgentLog` |
| 출력 | `list[MediaBrief]` (카피당 1개) |
| Claude | 선택 — 구조화 출력, mock 템플릿 폴백 |

`MediaBrief` 구성: 샷리스트(`Shot`: 초·장면·자막, 첫 컷=3초 후킹) · BGM 가이드 ·
이미지 생성 프롬프트(영문) · 영상 생성 프롬프트(영문, higgsfield 등에 붙여넣기용) ·
**`tts_script`** — 캡컷 텍스트읽기(TTS)에 그대로 붙일 나레이션 대본(카피 언어).

운영 흐름: kupas 가 프롬프트·대본 생성 → 사용자가 higgsfield 로 영상 생성(유료라
사용자 결정) → 캡컷 TTS+자동자막 → 업로드.

---

## ⑤ PublishAgent — `publish.py`

**역할**: 게시 준비 담당. 딥링크·광고고지를 조립해 게시 직전 콘텐츠로 만든다.
자동 게시는 하지 않는다(플랫폼 약관).

| | |
|--|--|
| 입력 | `Brief`, `ScoredProduct`, `list[Caption]`, `SourceProvider`, `AgentLog` |
| 출력 | `ContentPiece` (딥링크·subId·렌더본·점수 포함) |
| Claude | 없음 |

불변 규칙:

- **subId = `{prefix}-{platform}-{productId}-{runToken}`** (영숫자만, 40자).
  플랫폼별 분리(성과 귀속) + 게시물별 유니크(같은 상품 재게시 시 리포트 이중집계
  방지). 반드시 `make_subid()` 로 생성.
- **플랫폼마다 딥링크를 따로** 생성해 `platform_links`/`platform_subids`/`rendered`
  에 담는다. 출력·복붙은 `rendered[platform]` 사용.
- **광고 고지는 언어별** — `disclosure_for(brief.language)` (ko: 쿠팡 파트너스 고지,
  en: affiliate disclosure). 의무 표기이므로 제거 금지.

---

## Orchestrator — `orchestrator.py`

에이전트 사슬의 지휘자. 에이전트가 아니라 조율자다.

- `_market_brief()`: `brief.market` 으로 언어·통화를 채운 Brief 사본 생성
- `curate(brief)`: 발굴+선별만 (무료 triage, 카피·링크 없음)
- `run(brief)`: 단일 마켓 전체 사슬 (+`with_media` 시 미디어, `save` 시 SQLite 저장)
- `run_markets(brief)` / `curate_markets(brief)`: `market="all"` 이면 국내+글로벌을
  순차 실행해 결과를 합침
- 소스(`SourceProvider`)와 Claude 클라이언트를 **여기서 만들어 에이전트에 주입**

## 새 에이전트 추가 체크리스트

1. `kupas/agents/<name>.py` 에 `name`/`role`/`run(...)` 모듈 작성 — mock 폴백 필수
2. 필요한 입력은 Brief 필드로 (에이전트 안에서 환경변수·클라이언트 생성 금지)
3. `orchestrator.py` 에서 생성·주입 + `roster` 에 등록, `AgentLog` 로 근거 남기기
4. `agents/__init__.py` export, `tests/test_pipeline.py` 에 단위+통합 테스트
5. 이 README 에 섹션 추가
