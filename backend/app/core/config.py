from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "AIM Analyzer"
    openai_api_key: str = ""
    openweather_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./aimanalyzer.db"
    upload_dir: str = "./uploads"
    photo_dir: str = "./photos"
    max_upload_size_mb: int = 500
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.photo_dir).mkdir(parents=True, exist_ok=True)
