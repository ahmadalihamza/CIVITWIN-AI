from dataclasses import dataclass, field
from os import environ
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


def _boolean(name: str, default: bool) -> bool:
    value = environ.get(name)
    if value is None:
        return default
    if value.lower() not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false.")
    return value.lower() == "true"


def _integer(name: str, default: int, *, maximum: int) -> int:
    value = int(environ.get(name, str(default)))
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}.")
    return value


@dataclass(frozen=True)
class Settings:
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_port: int = 3000
    database_url: str = "sqlite:///./data/civitwin.db"
    demo_mode: bool = True
    ai_enabled: bool = False
    llm_model: str = ""
    llm_endpoint: str = ""
    llm_api_key: str = field(default="", repr=False)
    solver_timeout_seconds: int = 10
    stress_timeout_seconds: int = 60
    demo_path: Path = ROOT / "data/demo/bajaur-v1.json"
    web_origin: str = ""

    @property
    def allowed_origin(self) -> str:
        return self.web_origin or f"http://localhost:{self.web_port}"

    @property
    def provider_configured(self) -> bool:
        return self.ai_enabled and bool(self.llm_model.strip() and self.llm_endpoint.strip())

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        return cls(
            api_host=environ.get("API_HOST", "127.0.0.1"),
            api_port=_integer("API_PORT", 8000, maximum=65_535),
            web_port=_integer("WEB_PORT", 3000, maximum=65_535),
            database_url=environ.get("DATABASE_URL", "sqlite:///./data/civitwin.db"),
            demo_mode=_boolean("DEMO_MODE", True),
            ai_enabled=_boolean("AI_ENABLED", False),
            llm_model=environ.get("LLM_MODEL", ""),
            llm_endpoint=environ.get("LLM_ENDPOINT", ""),
            llm_api_key=environ.get("LLM_API_KEY", ""),
            solver_timeout_seconds=_integer("SOLVER_TIMEOUT_SECONDS", 10, maximum=300),
            stress_timeout_seconds=_integer("STRESS_TIMEOUT_SECONDS", 60, maximum=1_800),
            demo_path=Path(
                environ.get("DEMO_DATASET_PATH", str(ROOT / "data/demo/bajaur-v1.json"))
            ),
            web_origin=environ.get("WEB_ORIGIN", ""),
        )
