# Pretendard 서브셋

블로그 글에 실제로 쓰인 글자만 남긴 서브셋(각 ~44KB). **미리보기 전용**이다.

- 실제 블로거 글은 `tools/blogpost_template.html` 의 CDN 링크로 Pretendard 를 불러온다.
- 미리보기(아티팩트)는 외부 CDN 이 차단돼 폰트가 시스템 폰트로 떨어진다.
  그러면 디자인 판단이 불가능하므로 `tools/make_preview.py` 가 이 파일들을 data URI 로 심는다.

## 다시 만들기
글의 문구가 크게 바뀌어 글자가 깨져 보이면 다시 서브셋해야 한다.
```
pip install fonttools brotli
curl -o /tmp/Pretendard-Regular.woff2 https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/woff2/Pretendard-Regular.woff2
# (SemiBold, Bold 도 동일)
# 글에서 고유 문자를 뽑아 subset_chars.txt 로 저장한 뒤
python3 -m fontTools.subset /tmp/Pretendard-Regular.woff2 --text-file=subset_chars.txt --flavor=woff2 --output-file=assets/fonts/sub-Regular.woff2
```

Pretendard 는 SIL Open Font License 1.1 이다. 서브셋·재배포가 허용되며 라이선스 고지가 필요하다.
Copyright (c) 2021 Kil Hyung-jin — https://github.com/orioncactus/pretendard
