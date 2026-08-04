# 토스쇼핑 쉐어링크 Open API 연동

`tools/toss_api.py` 를 쓰기 위한 준비. **한 번만 하면 됩니다.**

---

## 왜 붙이나

지금까지 가격·재고 확인은 전부 사용자 몫이었습니다. 실제로 파우시가 한 주 만에
**34,920 → 28,570원**으로 바뀐 걸 캡처로야 알았고, 그때 이미 블로그 글의 숫자는
틀린 상태였습니다. 글이 늘어날수록 사람 눈으로는 못 잡습니다.

이 API 로 해결되는 것:

| | 전 | 후 |
|---|---|---|
| 가격·품절 | 사용자가 앱에서 확인 | `toss_api.py refresh` 한 줄 |
| 쉐어링크 | 앱에서 하나씩 복사 | `toss_api.py link <id>` |
| 상품 발굴 | 캡처를 받아서 정리 | 베스트·하루특가 조회 |

---

## 사용자가 할 일 (3단계)

### 1. 인증 정보 발급

`sharelink.toss.im` → **API 연동** 메뉴에서 직접 발급합니다.

- **Access Key** / **Secret Key** 한 쌍이 나옵니다
- ⚠️ **Secret Key 는 발급 직후 1회만 표시됩니다.** 바로 안전한 곳에 복사해 두세요
- 재발급하면 **같은 사업자의 기존 키가 즉시 무효**가 됩니다 (계정이 여럿이어도 키는 하나)
- **퍼블리셔 UUID(`publisherId`)** 도 함께 안내받습니다 — 링크 발급에 필요합니다

기본 스코프 두 개가 부여됩니다:

| 스코프 | 용도 |
|---|---|
| `sharelink:read` | 카테고리·상품 목록·상품 상세 조회 |
| `sharelink:write` | 쉐어링크 발급 |

### 2. 출발지 IP 등록  ← **여기서 제일 많이 막힙니다**

API 를 **호출하는 서버**의 IP 를 등록해야 합니다. 내 PC 가 아닙니다.

```
python3 tools/toss_api.py whoami
```

이 명령이 출력하는 IP 를 어드민에 등록하세요. 사업자당 최대 10개, 단일 IP 또는
CIDR 대역(`203.0.113.0/24`) 으로 넣을 수 있고, **운영·알파 환경에 각각** 등록해야 합니다.

> ⚠️ **이 세션 환경의 IP 는 고정이 아닙니다.**
> 컨테이너가 재생성되면 바뀔 수 있으므로, 호출 전 `whoami` 로 매번 확인하고
> 달라졌으면 어드민에서 추가 등록하세요. 등록 슬롯이 10개니 여유는 있습니다.
> 안정적으로 돌리려면 고정 IP 서버(집 서버·VPS)에서 실행하는 편이 낫습니다.

### 3. 키를 환경변수로 전달

```bash
export TOSS_ACCESS_KEY="발급받은 Access Key"
export TOSS_SECRET_KEY="발급받은 Secret Key"
export TOSS_PUBLISHER_ID="퍼블리셔 UUID"
```

🔴 **이 repo 는 공개입니다. 키를 파일에 쓰지 마세요.** 커밋되는 순간 노출됩니다.
토큰 캐시(`.toss_token.json`)는 `.gitignore` 에 등록해 뒀습니다.

---

## 확인

```bash
python3 tools/toss_api.py health --alpha    # 알파에서 먼저
python3 tools/toss_api.py health            # 운영
```

`✓ 인증·IP·라우팅 정상` 이 나오면 준비 완료입니다.

알파(테스트) 환경은 **키와 IP 가 운영과 분리**돼 있습니다. 먼저 알파에서 확인하고
운영으로 넘어가시길 권합니다.

---

## 쓰는 법

```bash
python3 tools/toss_api.py best --size 20             # 지금 잘 팔리는 상품
python3 tools/toss_api.py categories                 # 카테고리 트리
python3 tools/toss_api.py category-best <categoryId> # 카테고리별 베스트
python3 tools/toss_api.py deals                      # 하루특가
python3 tools/toss_api.py detail 12345,12346         # 최신 가격·품절 (최대 30건)
python3 tools/toss_api.py link 12345                 # 쉐어링크 발급
python3 tools/toss_api.py refresh posts_data/feeder.json   # 저장된 가격 일괄 갱신
```

`refresh` 를 쓰려면 `posts_data/*.json` 의 토스 상품에 `taca_item_id` 가 있어야 합니다.
기존 글은 캡처로 만들어서 이 값이 없으니, 한 번은 `best` 나 `detail` 로 찾아 채워야 합니다.

---

## 반드시 지킬 것

**수익은 `link` 로 발급한 링크로만 집계됩니다.**
조회 응답의 `productUrl` 은 추적이 안 됩니다. 게시글에 그걸 넣으면 수익이 0원입니다.
(일반 "공유하기" 링크가 0원인 것과 같은 함정입니다.)

**응답은 저장해서 재사용하세요.**
호출 한도가 파트너 단위 **10 rps**(버스트 30)입니다. 상품 랭킹은 하루 한 번 갱신되니
매번 부를 필요가 없고, 발급한 쉐어링크도 저장해 두고 재사용하면 됩니다.
`toss_api.py` 는 호출 간격을 자동으로 두고, 429 는 `Retry-After` 를 따라 재시도합니다.

**토큰은 재사용하세요.**
유효기간이 약 1년입니다. `toss_api.py` 가 `.toss_token.json` 에 캐시하고 만료 5분 전에
자동 갱신합니다. 매 호출마다 발급하면 이용이 제한될 수 있습니다.

**성공·실패는 `resultType` 으로 판별합니다.**
요청 값 오류 같은 건 HTTP 200 으로 내려오고 `resultType: "FAIL"` 에 담깁니다.
HTTP 상태 코드만 보면 실패를 성공으로 착각합니다.

---

## 문서

`sharelink-docs.toss.im` 은 GitBook 이라 **모든 페이지에 `.md` 를 붙이면 마크다운**으로
받을 수 있고, `/llms.txt` 에 전체 색인이 있습니다. 문서에 직접 질문도 됩니다:

```
GET https://sharelink-docs.toss.im/guide/open-api/api/link.md?ask=<질문>
```
