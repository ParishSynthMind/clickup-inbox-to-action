"""Settings, read from environment variables (optionally a local .env file).

Nothing secret lives in code. Every ClickUp ID is configurable so the same
code works against any workspace.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SERVICE_TYPES = [
    "Workspace setup",
    "Automation",
    "Integration / API",
    "AI assistant",
    "Consulting / other",
]


def load_dotenv(path: Path) -> None:
    """Tiny .env loader (KEY=VALUE lines). Real env vars always win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    clickup_token: str = ""
    webhook_secret: str = ""
    team_id: str = ""
    intake_list_id: str = ""
    ai_summary_field_id: str = ""
    ai_priority_field_id: str = ""
    service_types: list[str] = field(default_factory=lambda: list(DEFAULT_SERVICE_TYPES))
    llm_model: str = "claude-sonnet-5-5"
    host: str = "0.0.0.0"
    port: int = 8000
    post_comment: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path.cwd() / ".env")
        e = os.environ.get
        return cls(
            clickup_token=e("CLICKUP_API_TOKEN", ""),
            webhook_secret=e("CLICKUP_WEBHOOK_SECRET", ""),
            team_id=e("CLICKUP_TEAM_ID", ""),
            intake_list_id=e("CLICKUP_INTAKE_LIST_ID", ""),
            ai_summary_field_id=e("CLICKUP_AI_SUMMARY_FIELD_ID", ""),
            ai_priority_field_id=e("CLICKUP_AI_PRIORITY_FIELD_ID", ""),
            service_types=_split(e("SERVICE_TYPES", "")) or list(DEFAULT_SERVICE_TYPES),
            llm_model=e("LLM_MODEL", "claude-sonnet-5-5"),
            host=e("HOST", "0.0.0.0"),
            port=int(e("PORT", "8000")),
            post_comment=e("POST_COMMENT", "true").lower() != "false",
        )
