"""Photo analysis using GPT-5.4 Vision for tire wear and car setup detection."""

import base64
import json
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import TirePhotoResult, CarPhotoResult, PhotoType


def _get_client(api_key: str | None = None) -> AsyncOpenAI:
    key = api_key or settings.openai_api_key
    if not key:
        raise ValueError("OpenAI API key not configured. Please set it in Settings.")
    return AsyncOpenAI(api_key=key)


def _encode_image(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _image_media_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    return types.get(ext, "image/jpeg")


TIRE_ANALYSIS_PROMPT = """You are an expert motorsport tire analyst. Analyze this photo of a tire's tread surface.

Return a JSON object with these fields:
- "compound": string or null - tire brand and model if readable from sidewall (e.g. "Bridgestone RE-71R", "Hoosier A7")
- "wear_pattern": one of "even", "inside_heavy", "outside_heavy", "center_heavy", "cupping"
- "wear_severity_pct": number 0-100 representing estimated remaining tread life percentage
- "heat_evidence": one of "none", "graining", "blistering", "cording", "glazing"
- "condition_summary": one sentence summary of the tire's condition and any concerns

Only return the JSON object, no other text."""

CAR_ANALYSIS_PROMPT = """You are an expert motorsport engineer analyzing a track/race car photo. Identify the aerodynamic configuration and vehicle characteristics.

Return a JSON object with these fields:
- "aero_components": list of strings, any of: "splitter", "wing", "diffuser", "canards", "side_skirts", "louvers", "vortex_generators", "hood_vents", "brake_ducts"
- "aero_level": one of "none", "mild", "full"
  - "none": no visible aero components
  - "mild": 1-2 small components (small lip splitter, small wing)
  - "full": multiple aero components or large wing + splitter combo
- "vehicle_type": one of "sedan", "coupe", "hatchback", "convertible", "formula", "prototype", "kart", "suv", "truck", "other"
- "ride_height": one of "low", "stock", "raised"
- "notable_features": list of strings - other observations relevant to track use (e.g. "roll cage visible", "tow hooks", "stripped interior", "racing livery")

Only return the JSON object, no other text."""


async def analyze_tire_photo(file_path: str, api_key: str | None = None) -> TirePhotoResult:
    """Analyze a tire photo using GPT-4o Vision."""
    client = _get_client(api_key)
    b64 = _encode_image(file_path)
    media = _image_media_type(file_path)

    response = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": TIRE_ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media};base64,{b64}", "detail": "high"},
                    },
                ],
            }
        ],
        max_completion_tokens=500,
        temperature=0.2,
    )

    text = response.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(text)
        return TirePhotoResult(**data)
    except (json.JSONDecodeError, Exception):
        return TirePhotoResult(condition_summary=text)


async def analyze_car_photo(file_path: str, api_key: str | None = None) -> CarPhotoResult:
    """Analyze a car setup photo using GPT-4o Vision."""
    client = _get_client(api_key)
    b64 = _encode_image(file_path)
    media = _image_media_type(file_path)

    response = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CAR_ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media};base64,{b64}", "detail": "high"},
                    },
                ],
            }
        ],
        max_completion_tokens=500,
        temperature=0.2,
    )

    text = response.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(text)
        return CarPhotoResult(**data)
    except (json.JSONDecodeError, Exception):
        return CarPhotoResult(notable_features=[text])


async def analyze_photo(file_path: str, photo_type: PhotoType, api_key: str | None = None) -> dict:
    """Route photo analysis based on type."""
    if photo_type.value.startswith("tire_"):
        result = await analyze_tire_photo(file_path, api_key=api_key)
    else:
        result = await analyze_car_photo(file_path, api_key=api_key)
    return result.model_dump()
