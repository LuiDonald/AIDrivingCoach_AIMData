"""AI Coach chat endpoint with function calling."""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.db_models import Session, Lap, Corner, Photo, ChatMessageRecord
from app.models.schemas import ChatRequest, ChatResponse, SessionMetadata
from app.services.ai_coach import chat_with_coach, generate_coaching_report
from app.services.file_parser import parse_file
from app.services.track_segmentation import DetectedCorner, segment_lap_distance
from app.services.lap_analysis import (
    compute_theoretical_best,
    compute_consistency,
    compute_gg_data,
    get_speed_trace,
    get_braking_zones,
    analyze_corner_for_lap,
    compute_lap_summary,
)

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["ai-coach"])


async def _build_session_context(session_id: str, db: AsyncSession) -> dict:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    result = await db.execute(
        select(Lap).where(Lap.session_id == session_id).order_by(Lap.lap_number)
    )
    laps = result.scalars().all()

    return {
        "track": session.track_name or "Unknown",
        "driver": session.driver_name or "Unknown",
        "device": session.device_model or "Unknown",
        "date": str(session.session_date) if session.session_date else "Unknown",
        "num_laps": session.num_laps,
        "best_lap_time_s": session.best_lap_time_s,
        "best_lap_number": session.best_lap_number,
        "channels": session.channels_available or [],
        "metadata": session.metadata_json or {},
        "lap_times": [
            {"lap": l.lap_number, "time_s": l.lap_time_s}
            for l in laps
        ],
    }


async def _create_tool_executor(session_id: str, db: AsyncSession):
    """Create a tool executor that handles function calls from the LLM."""

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    parsed = parse_file(session.file_path)

    result = await db.execute(
        select(Lap).where(Lap.session_id == session_id).order_by(Lap.lap_number)
    )
    db_laps = result.scalars().all()
    laps = [
        {
            "lap_number": l.lap_number,
            "lap_time_s": l.lap_time_s,
            "start_time_ms": l.start_time_ms,
            "end_time_ms": l.end_time_ms,
        }
        for l in db_laps
    ]

    result = await db.execute(
        select(Corner).where(Corner.session_id == session_id).order_by(Corner.corner_id)
    )
    db_corners = result.scalars().all()
    corners = [
        DetectedCorner(
            corner_id=c.corner_id,
            corner_type=c.corner_type,
            start_distance_m=c.start_distance_m,
            end_distance_m=c.end_distance_m,
            apex_distance_m=c.apex_distance_m,
            apex_lateral_g=0,
            start_idx=0,
            end_idx=0,
            apex_idx=0,
        )
        for c in db_corners
    ]

    async def executor(fn_name: str, fn_args: dict) -> dict:
        sid = fn_args.get("session_id", session_id)

        if fn_name == "get_session_summary":
            return await _build_session_context(sid, db)

        elif fn_name == "get_lap_comparison":
            lap_a_num = fn_args["lap_a"]
            lap_b_num = fn_args["lap_b"]
            lap_a = next((l for l in laps if l["lap_number"] == lap_a_num), None)
            lap_b = next((l for l in laps if l["lap_number"] == lap_b_num), None)
            if not lap_a or not lap_b:
                return {"error": "Lap not found"}

            comparison = {"lap_a": lap_a, "lap_b": lap_b, "corners": []}
            for corner in corners:
                df_a = segment_lap_distance(parsed.df, lap_a["start_time_ms"], lap_a["end_time_ms"])
                df_b = segment_lap_distance(parsed.df, lap_b["start_time_ms"], lap_b["end_time_ms"])
                ca = analyze_corner_for_lap(df_a, corner)
                cb = analyze_corner_for_lap(df_b, corner)
                if ca and cb:
                    ca.lap_number = lap_a_num
                    cb.lap_number = lap_b_num
                    comparison["corners"].append({
                        "corner_id": corner.corner_id,
                        "corner_type": corner.corner_type,
                        "lap_a": ca.__dict__,
                        "lap_b": cb.__dict__,
                        "time_delta_s": round(ca.time_in_corner_s - cb.time_in_corner_s, 3),
                    })
            return comparison

        elif fn_name == "get_corner_analysis":
            cid = fn_args["corner_id"]
            corner = next((c for c in corners if c.corner_id == cid), None)
            if not corner:
                return {"error": f"Corner {cid} not found"}
            target = fn_args.get("lap_numbers") or [l["lap_number"] for l in laps]
            results = []
            for lap in laps:
                if lap["lap_number"] in target:
                    lap_df = segment_lap_distance(parsed.df, lap["start_time_ms"], lap["end_time_ms"])
                    a = analyze_corner_for_lap(lap_df, corner)
                    if a:
                        a.lap_number = lap["lap_number"]
                        results.append(a.__dict__)
            return {"corner_id": cid, "data": results}

        elif fn_name == "get_speed_trace":
            lap_nums = fn_args["lap_numbers"]
            traces = {}
            for lap in laps:
                if lap["lap_number"] in lap_nums:
                    traces[str(lap["lap_number"])] = get_speed_trace(parsed.df, lap)
            return traces

        elif fn_name == "get_consistency_report":
            return compute_consistency(parsed.df, laps, corners)

        elif fn_name == "get_braking_zones":
            ln = fn_args["lap_number"]
            lap = next((l for l in laps if l["lap_number"] == ln), None)
            if not lap:
                return {"error": f"Lap {ln} not found"}
            return {"lap_number": ln, "zones": get_braking_zones(parsed.df, lap, corners)}

        elif fn_name == "get_weather_conditions":
            return session.metadata_json.get("weather", {}) if session.metadata_json else {}

        elif fn_name == "get_tire_condition":
            result = await db.execute(
                select(Photo).where(
                    Photo.session_id == sid,
                    Photo.photo_type.like("tire_%"),
                )
            )
            photos = result.scalars().all()
            return {
                "tires": [
                    {"position": p.photo_type, "analysis": p.analysis_json}
                    for p in photos
                ]
            }

        elif fn_name == "get_car_setup":
            result = await db.execute(
                select(Photo).where(
                    Photo.session_id == sid,
                    Photo.photo_type.like("car_%"),
                )
            )
            photos = result.scalars().all()
            car_data = session.metadata_json.get("aero", {}) if session.metadata_json else {}
            car_photos = [
                {"angle": p.photo_type, "analysis": p.analysis_json}
                for p in photos
            ]
            return {"setup_metadata": car_data, "photo_analysis": car_photos}

        elif fn_name == "get_gg_diagram":
            ln = fn_args["lap_number"]
            lap = next((l for l in laps if l["lap_number"] == ln), None)
            if not lap:
                return {"error": f"Lap {ln} not found"}
            return compute_gg_data(parsed.df, lap)

        return {"error": f"Unknown function: {fn_name}"}

    return executor


@router.post("/chat", response_model=ChatResponse)
async def chat(
    session_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message to the AI driving coach."""
    context = await _build_session_context(session_id, db)
    executor = await _create_tool_executor(session_id, db)

    history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

    result = await chat_with_coach(
        session_id=session_id,
        user_message=request.message,
        conversation_history=history,
        session_context=context,
        tool_executor=executor,
    )

    db.add(ChatMessageRecord(
        session_id=session_id,
        role="user",
        content=request.message,
    ))
    db.add(ChatMessageRecord(
        session_id=session_id,
        role="assistant",
        content=result["message"],
        tool_calls=result.get("tool_calls_made"),
    ))
    await db.commit()

    return ChatResponse(
        message=result["message"],
        tool_calls_made=result.get("tool_calls_made", []),
    )


@router.get("/chat/history")
async def chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get chat history for a session."""
    result = await db.execute(
        select(ChatMessageRecord)
        .where(ChatMessageRecord.session_id == session_id)
        .order_by(ChatMessageRecord.created_at)
    )
    messages = result.scalars().all()
    return [
        {"role": m.role, "content": m.content, "created_at": str(m.created_at)}
        for m in messages
    ]


@router.post("/coaching-report")
async def generate_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """Generate an AI coaching report for the session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    parsed = parse_file(session.file_path)
    result = await db.execute(
        select(Lap).where(Lap.session_id == session_id).order_by(Lap.lap_number)
    )
    db_laps = result.scalars().all()
    laps = [
        {
            "lap_number": l.lap_number,
            "lap_time_s": l.lap_time_s,
            "start_time_ms": l.start_time_ms,
            "end_time_ms": l.end_time_ms,
        }
        for l in db_laps
    ]

    result = await db.execute(
        select(Corner).where(Corner.session_id == session_id).order_by(Corner.corner_id)
    )
    db_corners = result.scalars().all()
    corners = [
        DetectedCorner(
            corner_id=c.corner_id,
            corner_type=c.corner_type,
            start_distance_m=c.start_distance_m,
            end_distance_m=c.end_distance_m,
            apex_distance_m=c.apex_distance_m,
            apex_lateral_g=0, start_idx=0, end_idx=0, apex_idx=0,
        )
        for c in db_corners
    ]

    theoretical = compute_theoretical_best(parsed.df, laps, corners)
    consistency = compute_consistency(parsed.df, laps, corners)

    summary_data = {
        "track": session.track_name,
        "driver": session.driver_name,
        "num_laps": session.num_laps,
        "best_lap_time_s": session.best_lap_time_s,
        "best_lap_number": session.best_lap_number,
        "channels": session.channels_available,
        "metadata": session.metadata_json or {},
        "theoretical_best": theoretical,
        "consistency": consistency,
        "lap_summaries": [
            compute_lap_summary(parsed.df, lap)
            for lap in laps
        ],
    }

    report = await generate_coaching_report(summary_data)

    session.coaching_report_json = report
    await db.commit()

    return report
