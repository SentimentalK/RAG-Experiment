from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Base directory of the workspace (handles container directory structures gracefully)
_config_dir = Path(__file__).resolve().parent
if len(_config_dir.parents) >= 2 and _config_dir.parents[1].name == "backend":
    BASE_DIR = _config_dir.parents[2]
else:
    BASE_DIR = _config_dir.parents[1]




class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Sherlock RAG Lab"
    DEBUG: bool = True

    # Data Settings
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"

    # Alias Dataset Settings
    ALIAS_DATASET_PATH: Path = (
        BASE_DIR
        / "experiments"
        / "noun_units_v2a"
        / "candidates"
        / "review"
        / "sherlock_entity_alias_groups_final.json"
    )
    ALIAS_DATASET_EXPECTED_SHA256: str = "2b16f62f2537c0703985585a8e467cda14d0790a3fad3258c31439322cfd5dd7"
    ALIAS_DATASET_STRICT_VALIDATION: bool = True

    # Database Settings
    DATABASE_URL: str = "postgresql://rag_user:rag_password@localhost:5432/sherlock_rag"

    # Sherlock Book Specifics
    SHERLOCK_URL: str = "https://www.gutenberg.org/files/1661/1661-h/1661-h.htm"
    SHERLOCK_RAW_HTML_FILENAME: str = "sherlock_holmes_1661.html"
    SHERLOCK_METADATA_FILENAME: str = "source_metadata.json"

    # Groq Settings
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # CORS Settings
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    @property
    def raw_html_path(self) -> Path:
        return self.RAW_DATA_DIR / self.SHERLOCK_RAW_HTML_FILENAME

    @property
    def metadata_path(self) -> Path:
        return self.RAW_DATA_DIR / self.SHERLOCK_METADATA_FILENAME

    # Configuration for loading from environment variables or .env file
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

settings = Settings()
