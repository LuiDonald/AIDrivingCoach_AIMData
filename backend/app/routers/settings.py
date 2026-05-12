"""Settings endpoints: validate API keys for supported AI providers."""

from fastapi import APIRouter
from openai import AsyncOpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])

PROVIDER_BASE_URLS: dict[str, str] = {
    "deepseek": "https://api.deepseek.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


class ValidateKeyRequest(BaseModel):
    api_key: str
    provider: str = "openai"


class ValidateKeyResponse(BaseModel):
    valid: bool
    error: str | None = None


@router.post("/validate-key", response_model=ValidateKeyResponse)
async def validate_key(req: ValidateKeyRequest):
    """Test if an API key is valid by making a lightweight API call."""
    if not req.api_key:
        return ValidateKeyResponse(valid=False, error="API key is required.")

    if req.provider == "openai" and not req.api_key.startswith("sk-"):
        return ValidateKeyResponse(valid=False, error="Invalid key format. OpenAI keys should start with 'sk-'.")

    try:
        base_url = PROVIDER_BASE_URLS.get(req.provider)
        if base_url:
            client = AsyncOpenAI(api_key=req.api_key, base_url=base_url)
        else:
            client = AsyncOpenAI(api_key=req.api_key)
        await client.models.list()
        return ValidateKeyResponse(valid=True)
    except Exception as e:
        return ValidateKeyResponse(valid=False, error=str(e))
