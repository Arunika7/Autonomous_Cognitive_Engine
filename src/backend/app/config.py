from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]
possible_env_paths = [
    BASE_DIR / ".env",
    Path.cwd() / ".env",
    Path(__file__).parent.parent.parent / ".env",
    Path(__file__).parent / ".env",
    Path(".env")
]
env_file_path = next((p for p in possible_env_paths if p.is_file()), ".env")

class Settings(BaseSettings):
    # LLM Settings
    groq_api_key: str = ""
    supervisor_model: str = "llama-3.1-8b-instant"
    sub_agent_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.35
    max_tokens: int = 2048
    
    # API Security
    api_auth_key: str = "default-secret-key-change-in-production"
    
    # Observability
    langchain_tracing_v2: str = "false"
    langsmith_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=str(env_file_path),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
