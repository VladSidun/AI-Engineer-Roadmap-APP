import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]


def database_url() -> URL:
    password = os.getenv("QUEST_DB_PASSWORD")
    if not password:
        raise RuntimeError("Set QUEST_DB_PASSWORD")
    return URL.create(
        "postgresql+psycopg", username=os.getenv("QUEST_DB_USER", "quest"),
        password=password, host=os.getenv("QUEST_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("QUEST_DB_PORT", "5544")), database=os.getenv("QUEST_DB_NAME", "quest"),
    )


@dataclass(frozen=True)
class Config:
    port: int = 8000
    dev: bool = False
    static: Path | None = None

    @property
    def origins(self) -> set[str]:
        origins = {f"http://127.0.0.1:{self.port}"}
        if self.dev:
            origins.add("http://127.0.0.1:5173")
        return origins

    @property
    def hosts(self) -> set[str]:
        return {origin.removeprefix("http://") for origin in self.origins}

    @classmethod
    def from_env(cls) -> "Config":
        static = os.getenv("QUEST_STATIC")
        return cls(int(os.getenv("QUEST_PORT", "8000")), os.getenv("QUEST_DEV") == "1",
                   Path(static) if static else None)
