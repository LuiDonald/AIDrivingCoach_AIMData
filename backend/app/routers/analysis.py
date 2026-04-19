"""Analysis endpoints: speed traces, g-g diagram, corners, track map, improvement suggestions."""

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.db_models import Session, Lap, Corner
from app.services.file_parser import parse_file
from app.services.track_segmentation import DetectedCorner, segment_lap_distance
from app.services.lap_analysis import (
    compute_theoretical_best,
    compute_consistency,
    compute_gg_data,
    get_speed_trace,
    get_braking_zones,
    analyze_corner_for_lap,
    compare_laps,
    compute_advanced_lap_metrics,
)
from app.services.track_database import match_track, map_detected_to_known
from app.services.ai_coach import generate_comparison_coaching

KPH_TO_MPH = 0.621371


def _match_track_with_gps(session, parsed):
    """Match track by name first, then fall back to GPS coordinates."""
    venue = session.track_name or ""
    venue_meta = parsed.metadata.get("Venue") if parsed.metadata else None
    gps_lat = parsed.metadata.get("gps_lat") if parsed.metadata else None
    gps_lon = parsed.metadata.get("gps_lon") if parsed.metadata else None
    if gps_lat is None and "gps_lat" in parsed.df.columns:
        lat_vals = parsed.df["gps_lat"].dropna()
        if len(lat_vals) > 0:
            gps_lat = float(lat_vals.median())
            gps_lon = float(parsed.df["gps_lon"].dropna().median())
    return match_track(venue, venue_meta, gps_lat=gps_lat, gps_lon=gps_lon)


def _convert_result_to_mph(result: dict) -> dict:
    """Recursively convert _kph fields to _mph in a result dict."""
    out = {}
    for k, v in result.items():
        if k.endswith("_kph") and isinstance(v, (int, float)):
            out[k.replace("_kph", "_mph")] = round(v * KPH_TO_MPH, 1)
        elif isinstance(v, list):
            out[k] = [
                _convert_result_to_mph(item) if isinstance(item, dict) else item
                for item in v
            ]
        elif isinstance(v, dict):
            out[k] = _convert_result_to_mph(v)
        else:
            out[k] = v
    return out


router = APIRouter(prefix="/api/sessions/{session_id}/analysis", tags=["analysis"])
cross_router = APIRouter(prefix="/api/compare", tags=["compare"])


async def _load_session_data(session_id: str, db: AsyncSession):
    """Load session from DB and parse the file.

    If no corners are stored in the DB (e.g. legacy data parsed before
    lateral-g mapping was fixed), detect them live from the best lap.
    """
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

    if not corners and laps:
        from app.services.track_segmentation import detect_corners as _detect_corners
        best_lap = min(laps, key=lambda l: l["lap_time_s"])
        best_df = segment_lap_distance(parsed.df, best_lap["start_time_ms"], best_lap["end_time_ms"])
        corners = _detect_corners(best_df)
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
        if corners:
            await db.commit()

    return session, parsed, laps, corners


@router.get("/speed-trace")
async def speed_trace(
    session_id: str,
    lap_numbers: str = Query(..., description="Comma-separated lap numbers"),
    db: AsyncSession = Depends(get_db),
):
    """Get speed vs distance data for selected laps."""
    session, parsed, laps, _ = await _load_session_data(session_id, db)
    requested = [int(n.strip()) for n in lap_numbers.split(",")]

    traces = {}
    for lap in laps:
        if lap["lap_number"] in requested:
            traces[lap["lap_number"]] = get_speed_trace(parsed.df, lap)

    return traces


@router.get("/gg-diagram")
async def gg_diagram(
    session_id: str,
    lap_number: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get g-g diagram data for a specific lap."""
    session, parsed, laps, _ = await _load_session_data(session_id, db)
    lap = next((l for l in laps if l["lap_number"] == lap_number), None)
    if not lap:
        raise HTTPException(404, f"Lap {lap_number} not found")

    return compute_gg_data(parsed.df, lap)


@router.get("/theoretical-best")
async def theoretical_best(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Compute theoretical best lap time from fastest segments."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)
    result = compute_theoretical_best(parsed.df, laps, corners)

    known = _match_track_with_gps(session, parsed)
    if known and result.get("segment_sources"):
        corner_dicts = [
            {"corner_id": c.corner_id, "apex_distance_m": c.apex_distance_m}
            for c in corners
        ]
        mapped = map_detected_to_known(corner_dicts, known)
        name_map = {m["corner_id"]: m["name"] for m in mapped}
        for seg in result["segment_sources"]:
            if seg.get("corner_id") and seg["corner_id"] in name_map:
                seg["label"] = name_map[seg["corner_id"]]

    return result


@router.get("/consistency")
async def consistency(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get consistency analysis across laps."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)
    return compute_consistency(parsed.df, laps, corners)


@router.get("/corners")
async def corners_list(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all detected corners for the session."""
    result = await db.execute(
        select(Corner).where(Corner.session_id == session_id).order_by(Corner.corner_id)
    )
    db_corners = result.scalars().all()
    return [
        {
            "corner_id": c.corner_id,
            "corner_type": c.corner_type,
            "start_distance_m": c.start_distance_m,
            "end_distance_m": c.end_distance_m,
            "apex_distance_m": c.apex_distance_m,
        }
        for c in db_corners
    ]


@router.get("/corners/{corner_id}")
async def corner_analysis(
    session_id: str,
    corner_id: int,
    lap_numbers: str | None = Query(None, description="Comma-separated lap numbers, or omit for all"),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed corner analysis across laps."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)

    corner = next((c for c in corners if c.corner_id == corner_id), None)
    if not corner:
        raise HTTPException(404, f"Corner {corner_id} not found")

    target_laps = laps
    if lap_numbers:
        requested = [int(n.strip()) for n in lap_numbers.split(",")]
        target_laps = [l for l in laps if l["lap_number"] in requested]

    results = []
    for lap in target_laps:
        lap_df = segment_lap_distance(parsed.df, lap["start_time_ms"], lap["end_time_ms"])
        analysis = analyze_corner_for_lap(lap_df, corner)
        if analysis:
            analysis.lap_number = lap["lap_number"]
            results.append({
                "corner_id": analysis.corner_id,
                "lap_number": analysis.lap_number,
                "entry_speed_kph": analysis.entry_speed_kph,
                "min_speed_kph": analysis.min_speed_kph,
                "exit_speed_kph": analysis.exit_speed_kph,
                "max_lateral_g": analysis.max_lateral_g,
                "time_in_corner_s": analysis.time_in_corner_s,
                "braking_start_distance_m": analysis.braking_start_distance_m,
                "throttle_start_distance_m": analysis.throttle_start_distance_m,
            })

    return results


@router.get("/braking-zones")
async def braking_zones(
    session_id: str,
    lap_number: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get braking zone analysis for a specific lap."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)
    lap = next((l for l in laps if l["lap_number"] == lap_number), None)
    if not lap:
        raise HTTPException(404, f"Lap {lap_number} not found")

    return get_braking_zones(parsed.df, lap, corners)


@router.get("/compare")
async def compare_two_laps(
    session_id: str,
    lap_a: int = Query(..., description="Reference lap (typically the faster one)"),
    lap_b: int = Query(..., description="Comparison lap"),
    db: AsyncSession = Depends(get_db),
):
    """Compare two laps: time delta trace, speed difference, and corner-by-corner breakdown."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)

    lap_a_data = next((l for l in laps if l["lap_number"] == lap_a), None)
    lap_b_data = next((l for l in laps if l["lap_number"] == lap_b), None)
    if not lap_a_data:
        raise HTTPException(404, f"Lap {lap_a} not found")
    if not lap_b_data:
        raise HTTPException(404, f"Lap {lap_b} not found")

    result = compare_laps(parsed.df, lap_a_data, lap_b_data, corners)

    # Attach known corner names
    known = _match_track_with_gps(session, parsed)
    if known and result.get("corner_deltas"):
        corner_dicts = [
            {"corner_id": c.corner_id, "apex_distance_m": c.apex_distance_m}
            for c in corners
        ]
        mapped = map_detected_to_known(corner_dicts, known)
        name_map = {m["corner_id"]: m["name"] for m in mapped}
        for cd in result["corner_deltas"]:
            cd["corner_label"] = name_map.get(cd["corner_id"], f"Turn {cd['corner_id']}")
    else:
        for cd in result.get("corner_deltas", []):
            cd["corner_label"] = f"Turn {cd['corner_id']}"

    return result


@router.post("/compare/coaching")
async def compare_coaching(
    session_id: str,
    lap_a: int = Query(...),
    lap_b: int = Query(...),
    db: AsyncSession = Depends(get_db),
    x_openai_key: str | None = Header(None),
):
    """Generate AI coaching analysis for a same-session lap comparison."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)

    lap_a_data = next((l for l in laps if l["lap_number"] == lap_a), None)
    lap_b_data = next((l for l in laps if l["lap_number"] == lap_b), None)
    if not lap_a_data or not lap_b_data:
        raise HTTPException(404, "Lap not found")

    result = compare_laps(parsed.df, lap_a_data, lap_b_data, corners)

    known = _match_track_with_gps(session, parsed)
    if known and result.get("corner_deltas"):
        corner_dicts = [
            {"corner_id": c.corner_id, "apex_distance_m": c.apex_distance_m}
            for c in corners
        ]
        mapped = map_detected_to_known(corner_dicts, known)
        name_map = {m["corner_id"]: m["name"] for m in mapped}
        for cd in result["corner_deltas"]:
            cd["corner_label"] = name_map.get(cd["corner_id"], f"Turn {cd['corner_id']}")
    else:
        for cd in result.get("corner_deltas", []):
            cd["corner_label"] = f"Turn {cd['corner_id']}"

    adv_a = _convert_result_to_mph(compute_advanced_lap_metrics(parsed.df, lap_a_data, corners))
    adv_b = _convert_result_to_mph(compute_advanced_lap_metrics(parsed.df, lap_b_data, corners))
    result["advanced_metrics_lap_a"] = adv_a
    result["advanced_metrics_lap_b"] = adv_b

    coaching = await generate_comparison_coaching(result, api_key=x_openai_key or None)
    return coaching


@router.get("/track-info")
async def track_info(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get known track info and corner names for the session's venue."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)

    known = _match_track_with_gps(session, parsed)

    corner_list = [
        {
            "corner_id": c.corner_id,
            "corner_type": c.corner_type,
            "apex_distance_m": c.apex_distance_m,
            "start_distance_m": c.start_distance_m,
            "end_distance_m": c.end_distance_m,
        }
        for c in corners
    ]

    if known:
        mapped = map_detected_to_known(corner_list, known)
        return {
            "track_name": known["full_name"],
            "track_matched": True,
            "corners": mapped,
        }

    return {
        "track_name": (session.track_name or "") or "Unknown Track",
        "track_matched": False,
        "corners": [
            {**c, "label": str(c["corner_id"]), "name": f"Turn {c['corner_id']}", "description": ""}
            for c in corner_list
        ],
    }


@router.get("/track-map")
async def track_map(
    session_id: str,
    lap_number: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get GPS track outline with speed coloring and corner markers for a lap."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)
    lap = next((l for l in laps if l["lap_number"] == lap_number), None)
    if not lap:
        raise HTTPException(404, f"Lap {lap_number} not found")

    lap_df = segment_lap_distance(parsed.df, lap["start_time_ms"], lap["end_time_ms"])

    if "gps_lat" not in lap_df.columns or "gps_lon" not in lap_df.columns:
        raise HTTPException(400, "No GPS data available for track map")

    lat = lap_df["gps_lat"].values
    lon = lap_df["gps_lon"].values
    speed_kph = lap_df["speed_kph"].values if "speed_kph" in lap_df.columns else np.zeros(len(lat))
    speed_mph = speed_kph * KPH_TO_MPH
    distance = lap_df["distance_m"].values if "distance_m" in lap_df.columns else np.arange(len(lat))
    time_ms = lap_df["time_ms"].values

    total = len(lat)
    step = max(1, total // 500)
    indices = list(range(0, total, step))
    if indices[-1] != total - 1:
        indices.append(total - 1)

    points = []
    for i in indices:
        points.append({
            "lat": float(lat[i]),
            "lon": float(lon[i]),
            "speed_mph": round(float(speed_mph[i]), 1),
            "distance_m": round(float(distance[i]), 1),
            "time_ms": int(time_ms[i]),
        })

    # Match to known track for corner labels
    known = _match_track_with_gps(session, parsed)

    corner_markers = []
    for c in corners:
        apex_mask = np.abs(distance - c.apex_distance_m)
        apex_idx = int(np.argmin(apex_mask))
        if apex_idx < len(lat):
            marker = {
                "corner_id": c.corner_id,
                "corner_type": c.corner_type,
                "lat": float(lat[apex_idx]),
                "lon": float(lon[apex_idx]),
                "apex_distance_m": c.apex_distance_m,
            }
            corner_markers.append(marker)

    if known:
        corner_markers = map_detected_to_known(corner_markers, known)
    else:
        for m in corner_markers:
            m["label"] = str(m["corner_id"])
            m["name"] = f"Turn {m['corner_id']}"

    return {
        "points": points,
        "corners": corner_markers,
        "min_speed": round(float(np.nanmin(speed_mph)), 1),
        "max_speed": round(float(np.nanmax(speed_mph)), 1),
    }


@router.get("/corner-suggestions")
async def corner_suggestions(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate concrete, data-driven improvement suggestions per corner.

    Uses real corner names from the motorsport community when the track is known.
    All speeds in mph.
    """
    from app.services.lap_analysis import filter_flying_laps
    session, parsed, laps, corners = await _load_session_data(session_id, db)
    laps = filter_flying_laps(laps)

    if not corners:
        return {"suggestions": [], "summary": "No corners detected in session data."}

    # Resolve corner names from known track database
    known = _match_track_with_gps(session, parsed)
    corner_names: dict[int, str] = {}
    if known:
        corner_dicts = [
            {"corner_id": c.corner_id, "apex_distance_m": c.apex_distance_m}
            for c in corners
        ]
        mapped = map_detected_to_known(corner_dicts, known)
        for m in mapped:
            corner_names[m["corner_id"]] = m["name"]

    def _label(corner_id: int) -> str:
        return corner_names.get(corner_id, f"Turn {corner_id}")

    def _mph(kph: float) -> float:
        return kph * KPH_TO_MPH

    suggestions = []

    for corner in corners:
        corner_data_all = []
        for lap in laps:
            lap_df = segment_lap_distance(parsed.df, lap["start_time_ms"], lap["end_time_ms"])
            analysis = analyze_corner_for_lap(lap_df, corner)
            if analysis:
                analysis.lap_number = lap["lap_number"]
                corner_data_all.append(analysis)

        if len(corner_data_all) < 1:
            continue

        best = min(corner_data_all, key=lambda x: x.time_in_corner_s)
        worst = max(corner_data_all, key=lambda x: x.time_in_corner_s)
        time_spread = worst.time_in_corner_s - best.time_in_corner_s

        direction = "left" if corner.corner_type == "left" else "right"
        label = _label(corner.corner_id)

        if best.braking_start_distance_m is not None and len(corner_data_all) > 1:
            brake_points = [c.braking_start_distance_m for c in corner_data_all if c.braking_start_distance_m]
            if brake_points:
                latest_brake = max(brake_points)
                earliest_brake = min(brake_points)
                brake_diff = latest_brake - earliest_brake
                if brake_diff > 5:
                    brake_diff_ft = brake_diff * 3.281
                    suggestions.append({
                        "corner_id": corner.corner_id,
                        "corner_label": label,
                        "category": "braking",
                        "priority": "HIGH" if brake_diff > 15 else "MEDIUM",
                        "suggestion": f"Brake {brake_diff_ft:.0f} ft later at {label}. Your best braking point is at {latest_brake * 3.281:.0f} ft, but you sometimes brake as early as {earliest_brake * 3.281:.0f} ft.",
                        "estimated_gain_s": round(time_spread * 0.4, 2) if time_spread > 0.05 else None,
                        "data": {
                            "best_brake_ft": round(latest_brake * 3.281, 1),
                            "worst_brake_ft": round(earliest_brake * 3.281, 1),
                            "delta_ft": round(brake_diff_ft, 1),
                        },
                    })

        if len(corner_data_all) > 1:
            entry_speeds = [c.entry_speed_kph for c in corner_data_all]
            max_entry = _mph(max(entry_speeds))
            min_entry = _mph(min(entry_speeds))
            entry_diff = max_entry - min_entry
            if entry_diff > 2:
                suggestions.append({
                    "corner_id": corner.corner_id,
                    "corner_label": label,
                    "category": "entry_speed",
                    "priority": "HIGH" if entry_diff > 5 else "MEDIUM",
                    "suggestion": f"Carry {entry_diff:.0f} mph more into {label} ({direction}). Your fastest entry is {max_entry:.0f} mph but you sometimes enter at {min_entry:.0f} mph.",
                    "estimated_gain_s": round(time_spread * 0.3, 2) if time_spread > 0.05 else None,
                    "data": {
                        "best_entry_mph": round(max_entry, 1),
                        "worst_entry_mph": round(min_entry, 1),
                    },
                })

        min_speeds = [c.min_speed_kph for c in corner_data_all]
        max_min_speed = _mph(max(min_speeds))
        avg_min_speed = _mph(sum(min_speeds) / len(min_speeds))
        if max_min_speed - avg_min_speed > 2:
            suggestions.append({
                "corner_id": corner.corner_id,
                "corner_label": label,
                "category": "apex_speed",
                "priority": "MEDIUM",
                "suggestion": f"Carry {max_min_speed - avg_min_speed:.0f} mph more through the apex at {label}. Best apex speed: {max_min_speed:.0f} mph, average: {avg_min_speed:.0f} mph.",
                "estimated_gain_s": round(time_spread * 0.3, 2) if time_spread > 0.05 else None,
                "data": {
                    "best_apex_mph": round(max_min_speed, 1),
                    "avg_apex_mph": round(avg_min_speed, 1),
                },
            })

        if len(corner_data_all) > 1:
            exit_speeds = [c.exit_speed_kph for c in corner_data_all]
            max_exit = _mph(max(exit_speeds))
            min_exit = _mph(min(exit_speeds))
            exit_diff = max_exit - min_exit
            if exit_diff > 2:
                suggestions.append({
                    "corner_id": corner.corner_id,
                    "corner_label": label,
                    "category": "exit_speed",
                    "priority": "HIGH" if exit_diff > 5 else "MEDIUM",
                    "suggestion": f"Get {exit_diff:.0f} mph more exit speed out of {label}. Best exit: {max_exit:.0f} mph vs worst: {min_exit:.0f} mph. Focus on earlier, smoother throttle application.",
                    "estimated_gain_s": round(time_spread * 0.3, 2) if time_spread > 0.05 else None,
                    "data": {
                        "best_exit_mph": round(max_exit, 1),
                        "worst_exit_mph": round(min_exit, 1),
                    },
                })

        if best.throttle_start_distance_m is not None and len(corner_data_all) > 1:
            throttle_points = [c.throttle_start_distance_m for c in corner_data_all if c.throttle_start_distance_m]
            if throttle_points:
                earliest_throttle = min(throttle_points)
                latest_throttle = max(throttle_points)
                throttle_diff = latest_throttle - earliest_throttle
                if throttle_diff > 5:
                    throttle_diff_ft = throttle_diff * 3.281
                    suggestions.append({
                        "corner_id": corner.corner_id,
                        "corner_label": label,
                        "category": "throttle",
                        "priority": "HIGH" if throttle_diff > 15 else "MEDIUM",
                        "suggestion": f"Get on throttle {throttle_diff_ft:.0f} ft earlier exiting {label}. You pick up throttle as early as {earliest_throttle * 3.281:.0f} ft but sometimes wait until {latest_throttle * 3.281:.0f} ft.",
                        "estimated_gain_s": round(time_spread * 0.3, 2) if time_spread > 0.05 else None,
                        "data": {
                            "best_throttle_ft": round(earliest_throttle * 3.281, 1),
                            "worst_throttle_ft": round(latest_throttle * 3.281, 1),
                        },
                    })

        if len(corner_data_all) >= 1:
            for cd in corner_data_all:
                speed_drop_pct = (cd.entry_speed_kph - cd.min_speed_kph) / cd.entry_speed_kph * 100 if cd.entry_speed_kph > 0 else 0
                entry_mph = _mph(cd.entry_speed_kph)
                min_mph = _mph(cd.min_speed_kph)
                if speed_drop_pct < 5 and cd.max_lateral_g < 0.6 and entry_mph > 50:
                    suggestions.append({
                        "corner_id": corner.corner_id,
                        "corner_label": label,
                        "category": "flat_out",
                        "priority": "HIGH",
                        "suggestion": f"Stay flat through {label}. You only lose {speed_drop_pct:.0f}% speed ({entry_mph:.0f} to {min_mph:.0f} mph) with only {cd.max_lateral_g:.2f}g lateral load. This section can likely be taken flat out.",
                        "estimated_gain_s": round(cd.time_in_corner_s * 0.1, 2),
                        "data": {
                            "entry_mph": round(entry_mph, 1),
                            "min_mph": round(min_mph, 1),
                            "max_lateral_g": round(cd.max_lateral_g, 2),
                        },
                    })
                    break

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    suggestions.sort(key=lambda s: (priority_order.get(s["priority"], 2), -(s.get("estimated_gain_s") or 0)))

    total_gain = sum(s.get("estimated_gain_s") or 0 for s in suggestions)
    track_name = known["full_name"] if known else (venue or "this session")

    return {
        "suggestions": suggestions,
        "total_estimated_gain_s": round(total_gain, 2),
        "num_corners": len(corners),
        "track_name": track_name,
        "summary": f"Found {len(suggestions)} improvement opportunities across {len(corners)} corners at {track_name}. Estimated total gain: {total_gain:.2f}s.",
    }


@router.get("/advanced-metrics")
async def advanced_metrics(
    session_id: str,
    lap_number: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get advanced telemetry metrics for a lap: friction circle, trail-braking,
    throttle analysis, steering balance, and wheel slip per corner."""
    session, parsed, laps, corners = await _load_session_data(session_id, db)
    lap = next((l for l in laps if l["lap_number"] == lap_number), None)
    if not lap:
        raise HTTPException(404, f"Lap {lap_number} not found")

    return compute_advanced_lap_metrics(parsed.df, lap, corners)


# ---- Cross-session comparison ----

@cross_router.get("")
async def cross_session_compare(
    session_a: str = Query(..., description="Session ID for reference lap"),
    lap_a: int = Query(..., description="Lap number in session A"),
    session_b: str = Query(..., description="Session ID for comparison lap"),
    lap_b: int = Query(..., description="Lap number in session B"),
    db: AsyncSession = Depends(get_db),
):
    """Compare laps from two different sessions at the same track."""
    sess_a, parsed_a, laps_a, corners_a = await _load_session_data(session_a, db)
    sess_b, parsed_b, laps_b, corners_b = await _load_session_data(session_b, db)

    lap_a_data = next((l for l in laps_a if l["lap_number"] == lap_a), None)
    lap_b_data = next((l for l in laps_b if l["lap_number"] == lap_b), None)
    if not lap_a_data:
        raise HTTPException(404, f"Lap {lap_a} not found in session A")
    if not lap_b_data:
        raise HTTPException(404, f"Lap {lap_b} not found in session B")

    # Use corners from session A as the reference track layout
    result = compare_laps(
        parsed_a.df, lap_a_data, lap_b_data, corners_a,
        df_b_override=parsed_b.df,
    )

    # Add session info to the result
    result["session_a_id"] = session_a
    result["session_b_id"] = session_b
    result["session_a_name"] = sess_a.track_name or sess_a.filename
    result["session_b_name"] = sess_b.track_name or sess_b.filename
    result["session_a_date"] = str(sess_a.session_date) if sess_a.session_date else None
    result["session_b_date"] = str(sess_b.session_date) if sess_b.session_date else None

    # Attach known corner names
    known_a = _match_track_with_gps(sess_a, parsed_a)
    if known_a and result.get("corner_deltas"):
        corner_dicts = [
            {"corner_id": c.corner_id, "apex_distance_m": c.apex_distance_m}
            for c in corners_a
        ]
        mapped = map_detected_to_known(corner_dicts, known_a)
        name_map = {m["corner_id"]: m["name"] for m in mapped}
        for cd in result["corner_deltas"]:
            cd["corner_label"] = name_map.get(cd["corner_id"], f"Turn {cd['corner_id']}")
    else:
        for cd in result.get("corner_deltas", []):
            cd["corner_label"] = f"Turn {cd['corner_id']}"

    return result


@cross_router.post("/coaching")
async def cross_session_coaching(
    session_a: str = Query(...),
    lap_a: int = Query(...),
    session_b: str = Query(...),
    lap_b: int = Query(...),
    db: AsyncSession = Depends(get_db),
    x_openai_key: str | None = Header(None),
):
    """Generate AI coaching analysis for a cross-session lap comparison."""
    compare_response = await cross_session_compare(
        session_a=session_a, lap_a=lap_a,
        session_b=session_b, lap_b=lap_b,
        db=db,
    )
    return await generate_comparison_coaching(compare_response, api_key=x_openai_key or None)
