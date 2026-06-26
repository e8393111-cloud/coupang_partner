"""환경설정 로딩. `.env` 또는 OS 환경변수에서 키를 읽는다."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv 미설치 시에도 OS 환경변수로 동작
    pass


@dataclass
class Config:
    coupang_access_key: str | None
    coupang_secret_key: str | None
    anthropic_api_key: str | None
    caption_model: str
    subid_prefix: str
    db_path: str
    make_webhook: str | None = None

    @property
    def has_coupang(self) -> bool:
        return bool(self.coupang_access_key and self.coupang_secret_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @classmethod
    def load(cls) -> "Config":
        return cls(
            coupang_access_key=os.getenv("COUPANG_ACCESS_KEY") or None,
            coupang_secret_key=os.getenv("COUPANG_SECRET_KEY") or None,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            caption_model=os.getenv("KUPAS_CAPTION_MODEL", "claude-opus-4-8"),
            subid_prefix=os.getenv("KUPAS_SUBID_PREFIX", "kupas"),
            db_path=os.getenv("KUPAS_DB_PATH", "kupas.db"),
            make_webhook=os.getenv("KUPAS_MAKE_WEBHOOK") or None,
        )
