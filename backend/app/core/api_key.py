"""Extract optional OpenAI API key from request header."""

from fastapi import Header


async def get_openai_key(
    x_openai_key: str | None = Header(None, alias="X-OpenAI-Key"),
) -> str | None:
    """FastAPI dependency that extracts the OpenAI key from the request header."""
    return x_openai_key or None
