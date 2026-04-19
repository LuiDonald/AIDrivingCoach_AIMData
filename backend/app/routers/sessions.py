"""Session management: upload, list, get details, update metadata."""

import hashlib
import uuid
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.db_models import Session, Lap, Corner
from app.models.schemas import SessionResponse, SessionMetadata, LapSummary
from app.services.file_parser import parse_file
from app.services.track_segmentation import detect_corners
from app.services.lap_analysis import compute_lap_summary, compute_theoretical_best, compute_consistency
from app.services.weather_service import fetch_weather

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
async def upload_session(
    file: UploadFile = File(...),
    metadata_json: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload and parse a telemetry file (.xrk, .xrz, or .csv)."""
    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in (".xrk", ".xrz", ".csv"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Use .xrk, .xrz, or .csv")

    file_bytes = await file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    existing = await db.execute(select(Session).where(Session.file_hash == file_hash))
    existing_session = existing.scalar_one_or_none()
    if existing_session:
        raise HTTPException(
            409,
            detail={
                "message": f"This file has already been uploaded as '{existing_session.filename}'",
                "existing_session_id": existing_session.id,
            },
        )

    session_id = str(uuid.uuid4())
    save_dir = Path(settings.upload_dir) / session_id
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / (file.filename or "unknown")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    try:
        parsed = parse_file(str(file_path))
    except Exception as e:
        shutil.rmtree(save_dir, ignore_errors=True)
        raise HTTPException(400, f"Failed to parse file: {str(e)}")

    metadata = None
    if metadata_json:
        import json
        try:
            metadata = SessionMetadata(**json.loads(metadata_json))
        except Exception:
            pass

    file_meta = parsed.metadata
    track_name = file_meta.get("Venue") or file_meta.get("venue") or file_meta.get("Track")
    session_date_str = file_meta.get("Log Date") or file_meta.get("Date")
    session_date = None
    if session_date_str:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                session_date = datetime.strptime(session_date_str, fmt)
                break
            except ValueError:
                continue

    best_lap = min(parsed.laps, key=lambda l: l["lap_time_s"]) if parsed.laps else None

    db_session = Session(
        id=session_id,
        filename=file.filename or "unknown",
        file_path=str(file_path),
        file_hash=file_hash,
        track_name=track_name,
        venue=track_name,
        session_date=session_date,
        device_model=file_meta.get("Logger Model") or file_meta.get("Device Name"),
        driver_name=metadata.driver_name if metadata else file_meta.get("Driver"),
        num_laps=len(parsed.laps),
        best_lap_time_s=best_lap["lap_time_s"] if best_lap else None,
        best_lap_number=best_lap["lap_number"] if best_lap else None,
        channels_available=parsed.channels,
        metadata_json=metadata.model_dump() if metadata else None,
    )
    db.add(db_session)

    for lap in parsed.laps:
        summary = compute_lap_summary(parsed.df, lap)
        db_lap = Lap(
            session_id=session_id,
            lap_number=lap["lap_number"],
            lap_time_s=lap["lap_time_s"],
            start_time_ms=lap["start_time_ms"],
            end_time_ms=lap["end_time_ms"],
            max_speed_kph=summary["max_speed_kph"],
            avg_lateral_g=summary["avg_lateral_g"],
            max_lateral_g=summary["max_lateral_g"],
            max_braking_g=summary["max_braking_g"],
        )
        db.add(db_lap)

    if best_lap and parsed.laps:
        from app.services.track_segmentation import segment_lap_distance
        best_lap_df = segment_lap_distance(parsed.df, best_lap["start_time_ms"], best_lap["end_time_ms"])
        corners = detect_corners(best_lap_df)
        for c in corners:
            db_corner = Corner(
                session_id=session_id,
                corner_id=c.corner_id,
                corner_type=c.corner_type,
                start_distance_m=c.start_distance_m,
                end_distance_m=c.end_distance_m,
                apex_distance_m=c.apex_distance_m,
            )
            db.add(db_corner)

    # Auto-fetch weather if GPS data is available
    if "gps_lat" in parsed.df.columns and "gps_lon" in parsed.df.columns:
        lat = parsed.df["gps_lat"].dropna().median()
        lon = parsed.df["gps_lon"].dropna().median()
        if lat and lon:
            weather = await fetch_weather(lat, lon, session_date)
            if weather and metadata is None:
                metadata = SessionMetadata()
            if weather and metadata:
                from app.models.schemas import WeatherData
                metadata.weather = WeatherData(**weather)
                db_session.metadata_json = metadata.model_dump()

    await db.commit()
    await db.refresh(db_session)

    return SessionResponse(
        id=db_session.id,
        filename=db_session.filename,
        track_name=db_session.track_name,
        venue=db_session.venue,
        session_date=db_session.session_date,
        device_model=db_session.device_model,
        num_laps=db_session.num_laps,
        best_lap_time_s=db_session.best_lap_time_s,
        best_lap_number=db_session.best_lap_number,
        metadata=SessionMetadata(**db_session.metadata_json) if db_session.metadata_json else None,
        channels_available=db_session.channels_available or [],
        created_at=db_session.created_at,
    )


@router.get("", response_model=list[SessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all uploaded sessions."""
    result = await db.execute(select(Session).order_by(Session.created_at.desc()))
    sessions = result.scalars().all()
    return [
        SessionResponse(
            id=s.id,
            filename=s.filename,
            track_name=s.track_name,
            venue=s.venue,
            session_date=s.session_date,
            device_model=s.device_model,
            num_laps=s.num_laps,
            best_lap_time_s=s.best_lap_time_s,
            best_lap_number=s.best_lap_number,
            metadata=SessionMetadata(**s.metadata_json) if s.metadata_json else None,
            channels_available=s.channels_available or [],
            created_at=s.created_at,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session details."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return SessionResponse(
        id=session.id,
        filename=session.filename,
        track_name=session.track_name,
        venue=session.venue,
        session_date=session.session_date,
        device_model=session.device_model,
        num_laps=session.num_laps,
        best_lap_time_s=session.best_lap_time_s,
        best_lap_number=session.best_lap_number,
        metadata=SessionMetadata(**session.metadata_json) if session.metadata_json else None,
        channels_available=session.channels_available or [],
        created_at=session.created_at,
    )


@router.get("/{session_id}/laps", response_model=list[LapSummary])
async def get_laps(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get all laps for a session."""
    result = await db.execute(
        select(Lap).where(Lap.session_id == session_id).order_by(Lap.lap_number)
    )
    laps = result.scalars().all()
    if not laps:
        raise HTTPException(404, "No laps found")

    best_time = min(l.lap_time_s for l in laps)
    return [
        LapSummary(
            lap_number=l.lap_number,
            lap_time_s=l.lap_time_s,
            delta_to_best_s=round(l.lap_time_s - best_time, 3),
            max_speed_kph=l.max_speed_kph,
            avg_lateral_g=l.avg_lateral_g,
            max_lateral_g=l.max_lateral_g,
            max_braking_g=l.max_braking_g,
        )
        for l in laps
    ]


@router.patch("/{session_id}/metadata")
async def update_metadata(
    session_id: str,
    metadata: SessionMetadata,
    db: AsyncSession = Depends(get_db),
):
    """Update session metadata (car info, tires, notes, etc)."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    session.metadata_json = metadata.model_dump()
    if metadata.driver_name:
        session.driver_name = metadata.driver_name
    await db.commit()
    return {"status": "updated"}


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session and its associated files."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    upload_dir = Path(settings.upload_dir) / session_id
    shutil.rmtree(upload_dir, ignore_errors=True)

    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}
