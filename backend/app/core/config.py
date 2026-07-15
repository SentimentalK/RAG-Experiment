from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Base directory of the workspace
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Sherlock RAG Lab"
    DEBUG: bool = True

    # Data Settings
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"

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

    @property
    def raw_html_path(self) -> Path:
        return self.RAW_DATA_DIR / self.SHERLOCK_RAW_HTML_FILENAME

    @property
    def metadata_path(self) -> Path:
        return self.RAW_DATA_DIR / self.SHERLOCK_METADATA_FILENAME

    # Configuration for loading from environment variables or .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
