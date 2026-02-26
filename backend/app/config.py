from pathlib import Path

from pydantic_settings import BaseSettings


# .env lives at project root (parent of backend/)
_here = Path(__file__).resolve().parent
_env_path = _here.parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    database_url: str

    # OpenAI
    openai_api_key: str

    # Hatchet
    hatchet_client_token: str

    model_config = {
        "env_file": _env_path,
        "extra": "ignore",
    }


# Single instance imported everywhere
settings = Settings()