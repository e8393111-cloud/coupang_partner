# CLAUDE.md — kupas 프로젝트 가이드

숏폼(스레드·틱톡·릴스·쇼츠) 제휴 수익화 파이프라인. 국내(쿠팡 파트너스)와
글로벌(Amazon·AliExpress)을 **한 번의 실행으로 동시 처리**한다.

## 자주 쓰는 명령

```bash
pip install -r requirements.txt          # 의존성 (anthropic, requests, pydantic, dotenv)
python tests/test_pipeline.py            # 전체 스모크 테스트 (pytest 불필요, 단독 실행)
python -m kupas agents                   # 에이전트 로스터 확인
python -m kupas run --market all --keyword "무선 청소기" --top 3 --audience 40+ --media
python -m kupas discover --market global --keyword "massager" --top 5   # 카피 없이 선별만(무료)
```

- `--keyword` 는 선택 — 없으면 TrendAgent 가 니치·시즌으로 자동 발굴.
- 테스트·실행 후 생기는 `kupas.db` 는 커밋 금지(.gitignore 됨). 루트에 남았으면 삭제.

## 아키텍처 (핵심 규칙)

```
Brief(마켓·키워드·플랫폼·타깃) ─▶ Orchestrator
  ⓪ Trend(키워드 자동) ▶ ① Discovery ▶ ② Curation ▶ ③ Copy ▶ ④ Compliance(검수)
  ▶ ⑤ Media(선택) ▶ ⑥ Publish     ⑦ Insight: 성과→카테고리 부스트→②에 되먹임
```

- `--keyword` 없이도 돈다(Trend 가 니치·시즌으로 발굴). `--niche` 로 힌트.
- 검수(Compliance)는 규칙 기반이라 항상 실행 — 효능 단정·과장 표현 자동 순화,
  순화 불가 건은 로그에 ⚠ 로 표시되므로 게시 전 확인.
- `python -m kupas insights` — 성과 분석·추천·학습 부스트 확인.

- **에이전트 = 역할 + `run(입력)→출력` 모듈** (`kupas/agents/`). 자율 도구루프 없음,
  지능이 필요한 곳만 Claude(`claude-opus-4-8`) 호출. 상세: `kupas/agents/README.md`.
- **모든 외부 의존은 mock 폴백 필수.** API 키가 하나도 없어도 전체 사슬이 돌아야 한다.
  새 기능도 mock 모드에서 끝까지 검증할 것 (`Config.has_coupang/has_anthropic` 참고).
- **마켓 추상화**(`kupas/sources.py`): `kr`=쿠팡/ko/KRW, `global`=Amazon/en/USD,
  `ali`=AliExpress/en/USD, `all`=kr+global. 마켓이 언어·통화·광고고지를 결정한다.
  Orchestrator 의 `_market_brief()` 가 Brief 에 채워 넣는다.
- **에이전트에 클라이언트를 직접 만들지 말 것** — 소스(`SourceProvider`)와 llm 은
  Orchestrator 가 주입한다.

## 불변 규칙 (깨면 돈이 샌다)

1. **subId 는 `{prefix}-{platform}-{productId}-{runToken}`** (영숫자만, 40자 컷).
   플랫폼별 분리(스레드/틱톡 성과 귀속) + 게시물별 유니크(리포트 이중집계 방지).
   `publish.make_subid()` 외의 경로로 subId 를 만들지 말 것.
2. **광고 고지 자동 삽입** — `publish.disclosure_for(language)`. 한국어(쿠팡 파트너스
   고지)/영어(affiliate disclosure) 모두 의무 표기. 카피 본문에는 넣지 않는다
   (렌더 시 시스템이 붙임 — Claude 프롬프트에도 그렇게 지시돼 있음).
3. **터미널 출력은 `piece.rendered[platform]`** 을 사용 — 플랫폼별 링크가 든 렌더본.
   대표 `piece.deeplink` 로 전 플랫폼을 찍으면 귀속이 깨진다(과거 Codex 리뷰 P2).
4. **키워드 확장 후 소스 조회는 올림 나눗셈**(`discovery.py`) — floor 면 under-fetch.
5. **성과 리포트 import 는 덮어쓰기**(누적값 가정, `storage.import_report`).

## Claude API 사용 패턴

- 구조화 출력: `client.messages.parse(..., output_format=PydanticModel)` +
  `thinking={"type": "adaptive"}`. `parsed_output` 이 None 이면 mock 폴백.
- 카피/미디어 프롬프트는 언어 분기(`ko`/`en`) — `captions._system_for()`,
  few-shot 은 `exemplars.fewshot_block(platform, language)`.

## 스타일

- 한국어 주석/독스트링, 파일 맨 위에 모듈 역할 설명.
- dataclass 우선, 타입힌트 필수(`from __future__ import annotations`).
- 테스트는 `tests/test_pipeline.py` 에 함수 추가 — 파일 하단 러너가 자동 수집하며
  pytest 없이 돈다. 새 동작에는 회귀 테스트를 같이 넣을 것.

## 운영 맥락 (설계 판단의 이유)

- 쿠팡 Open API 키는 **최종승인 후** 발급(첫 매출 조건) — 그전까지 mock 개발.
- 자동 게시는 플랫폼 앱심사가 필요해 **반자동**(queue/export/push→Make)이 정책.
- 영상 생성은 유료(higgsfield) — kupas 는 **프롬프트·캡컷 TTS 대본까지만** 만들고,
  실제 생성은 사용자가 결정한다. 코드에서 임의로 생성 API 를 붙이지 말 것.
- 타깃: 글로벌 40+ (릴스/쇼츠 중심, 혜택 중심 톤) + 국내 병행.
