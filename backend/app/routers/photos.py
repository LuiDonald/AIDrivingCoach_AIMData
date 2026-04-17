"""Photo upload and analysis endpoints for tires and car setup."""

import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.db_models import Session, Photo
from app.models.schemas import PhotoType
from app.services.photo_analysis import analyze_photo

router = APIRouter(prefix="/api/sessions/{session_id}/photos", tags=["photos"])


@router.post("/analyze")
async def upload_and_analyze_photo(
    session_id: str,
    photo_type: PhotoType = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    x_openai_key: str | None = Header(None),
):
    """Upload a photo (tire or car) and analyze it with GPT-4o Vision."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    ext = Path(file.filename or "photo.jpg").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(400, "Unsupported image format. Use JPG, PNG, or WebP.")

    photo_dir = Path(settings.photo_dir) / session_id
    photo_dir.mkdir(parents=True, exist_ok=True)
    photo_id = str(uuid.uuid4())
    file_path = photo_dir / f"{photo_type.value}_{photo_id}{ext}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        analysis = await analyze_photo(str(file_path), photo_type, api_key=x_openai_key or None)
    except Exception as e:
        analysis = {"error": str(e)}

    existing = await db.execute(
        select(Photo).where(
            Photo.session_id == session_id,
            Photo.photo_type == photo_type.value,
        )
    )
    old_photo = existing.scalar_one_or_none()
    if old_photo:
        old_path = Path(old_photo.file_path)
        if old_path.exists():
            old_path.unlink()
        old_photo.file_path = str(file_path)
        old_photo.analysis_json = analysis
    else:
        db.add(Photo(
            session_id=session_id,
            photo_type=photo_type.value,
            file_path=str(file_path),
            analysis_json=analysis,
        ))

    if photo_type.value.startswith("car_") and "aero_level" in analysis:
        meta = session.metadata_json or {}
        meta["aero"] = {
            "aero_level": analysis.get("aero_level", "none"),
            "components": analysis.get("aero_components", []),
            "vehicle_type": analysis.get("vehicle_type"),
            "ride_height": analysis.get("ride_height"),
            "notable_features": analysis.get("notable_features", []),
        }
        session.metadata_json = meta

    await db.commit()

    return {
        "photo_type": photo_type.value,
        "analysis": analysis,
        "file_path": str(file_path),
    }


@router.get("")
async def list_photos(session_id: str, db: AsyncSession = Depends(get_db)):
    """List all photos for a session with their analysis results."""
    result = await db.execute(
        select(Photo).where(Photo.session_id == session_id).order_by(Photo.created_at)
    )
    photos = result.scalars().all()
    return [
        {
            "id": p.id,
            "photo_type": p.photo_type,
            "analysis": p.analysis_json,
            "created_at": str(p.created_at),
        }
        for p in photos
    ]
