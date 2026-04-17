"""Settings endpoints: validate OpenAI API key."""

from fastapi import APIRouter
from openai import AsyncOpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ValidateKeyRequest(BaseModel):
    api_key: str


class ValidateKeyResponse(BaseModel):
    valid: bool
    error: str | None = None


@router.post("/validate-key", response_model=ValidateKeyResponse)
async def validate_key(req: ValidateKeyRequest):
    """Test if an OpenAI API key is valid by making a lightweight API call."""
    if not req.api_key or not req.api_key.startswith("sk-"):
        return ValidateKeyResponse(valid=False, error="Invalid key format. Key should start with 'sk-'.")

    try:
        client = AsyncOpenAI(api_key=req.api_key)
        await client.models.list()
        return ValidateKeyResponse(valid=True)
    except Exception as e:
        return ValidateKeyResponse(valid=False, error=str(e))
