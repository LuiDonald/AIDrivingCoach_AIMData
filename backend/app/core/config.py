from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AIM Analyzer"
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    max_upload_size_mb: int = 500
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
