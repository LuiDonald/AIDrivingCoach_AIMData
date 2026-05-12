"""Stateless analysis endpoints.

Files are uploaded, parsed in memory, and results are returned.
A short-lived in-memory cache keyed by token allows follow-up queries
(speed traces, comparisons, coaching, chat) without re-uploading.
"""

import json
import uuid
from collections import OrderedDict
from time import time as _now

import numpy as np
from fastapi import APIRouter, Header, HTTPException, Query, UploadFile, File

from app.services.file_parser import parse_file_bytes, ParsedSession
from app.services.track_segmentation import DetectedCorner, segment_lap_distance, detect_corners
from app.services.lap_analysis import (
    compute_theoretical_best,
    compute_consistency,
    compute_gg_data,
    compute_lap_summary,
    get_speed_trace,
    get_braking_zones,
    analyze_corner_for_lap,
    compare_laps,
    compute_advanced_lap_metrics,
    filter_flying_laps,
)
from app.services.track_database import match_track, map_detected_to_known, corners_from_known_track
from app.services.ai_coach import generate_coaching_report, generate_comparison_coaching, chat_with_coach
from app.services.weather_service import fetch_session_weather

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

KPH_TO_MPH = 0.621371
MAX_CACHE_ENTRIES = 50

# ---------------------------------------------------------------------------
# In-memory cache for parsed sessions (no TTL — sessions live until cleared
# by the user or evicted when MAX_CACHE_ENTRIES is exceeded)
# ---------------------------------------------------------------------------

_cache: OrderedDict[str, tuple[float, ParsedSession, list, list[DetectedCorner], dict | None]] = OrderedDict()


def _cache_cleanup():
    while len(_cache) > MAX_CACHE_ENTRIES:
        _cache.popitem(last=False)


def _cache_put(token: str, parsed: ParsedSession, laps: list, corners: list[DetectedCorner], weather: dict | None = None):
    _cache_cleanup()
    _cache[token] = (_now(), parsed, laps, corners, weather)


def _cache_get(token: str) -> tuple[ParsedSession, list, list[DetectedCorner]]:
    entry = _cache.get(token)
    if entry is None:
        raise HTTPException(404, "Analysis session not found. Please re-upload your file.")
    _ts, parsed, laps, corners, _weather = entry
    return parsed, laps, corners


def _cache_get_weather(token: str) -> dict | None:
    entry = _cache.get(token)
    if entry is None:
        return None
    return entry[4]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match_track_with_parsed(parsed: ParsedSession):
    """Match track by metadata name or GPS coordinates."""
    venue = ""
    venue_meta = parsed.metadata.get("Venue") if parsed.metadata else None
    gps_lat = parsed.metadata.get("gps_lat") if parsed.metadata else None
    gps_lon = parsed.metadata.get("gps_lon") if parsed.metadata else None
    if gps_lat is None and "gps_lat" in parsed.df.columns:
        lat_vals = parsed.df["gps_lat"].dropna()
        if len(lat_vals) > 0:
            gps_lat = float(lat_vals.median())
            gps_lon = float(parsed.df["gps_lon"].dropna().median())
    track_name = parsed.metadata.get("Venue") or parsed.metadata.get("venue") or parsed.metadata.get("Track") or ""
    return match_track(track_name, venue_meta, gps_lat=gps_lat, gps_lon=gps_lon)


def _convert_result_to_mph(result: dict) -> dict:
    out = {}
    for k, v in result.items():
        if k.endswith("_kph") and isinstance(v, (int, float)):
            out[k.replace("_kph", "_mph")] = round(v * KPH_TO_MPH, 1)
        elif isinstance(v, list):
            out[k] = [_convert_result_to_mph(item) if isinstance(item, dict) else item for item in v]
        elif isinstance(v, dict):
            out[k] = _convert_result_to_mph(v)
        else:
            out[k] = v
    return out


def _corner_data_to_mph(d: dict) -> dict:
    out = dict(d)
    for k in ("entry_speed_kph", "min_speed_kph", "exit_speed_kph"):
        if k in out:
            out[k.replace("_kph", "_mph")] = round(out.pop(k) * KPH_TO_MPH, 1)
    return out


def _build_name_map(corners: list[DetectedCorner], known: dict | None) -> dict[int, str]:
    """Build corner_id → corner name mapping.

    Uses direct mapping when corner count matches the database (DB-derived
    corners), otherwise falls back to distance-based matching.
    """
    if not known:
        return {c.corner_id: f"Turn {c.corner_id}" for c in corners}
    known_corners = known.get("corners", [])
    if len(corners) == len(known_corners):
        return {c.corner_id: kc.name for c, kc in zip(corners, known_corners)}
    corner_dicts = [{"corner_id": c.corner_id, "apex_distance_m": c.apex_distance_m} for c in corners]
    mapped = map_detected_to_known(corner_dicts, known)
    return {m["corner_id"]: m["name"] for m in mapped}


def _build_label_map(corners: list[DetectedCorner], known: dict | None) -> dict[int, str]:
    """Build corner_id → short label mapping (e.g. "3a", "12")."""
    if not known:
        return {c.corner_id: str(c.corner_id) for c in corners}
    known_corners = known.get("corners", [])
    if len(corners) == len(known_corners):
        return {c.corner_id: kc.number for c, kc in zip(corners, known_corners)}
    corner_dicts = [{"corner_id": c.corner_id, "apex_distance_m": c.apex_distance_m} for c in corners]
    mapped = map_detected_to_known(corner_dicts, known)
    return {m["corner_id"]: m.get("label", str(m["corner_id"])) for m in mapped}


def _build_corner_info(corners: list[DetectedCorner], known: dict | None) -> list[dict]:
    """Build full corner info list with labels, names, and descriptions."""
    if not known:
        return [
            {"corner_id": c.corner_id, "corner_type": c.corner_type,
             "apex_distance_m": c.apex_distance_m, "start_distance_m": c.start_distance_m,
             "end_distance_m": c.end_distance_m, "label": str(c.corner_id),
             "name": f"Turn {c.corner_id}", "description": ""}
            for c in corners
        ]
    known_corners = known.get("corners", [])
    if len(corners) == len(known_corners):
        return [
            {"corner_id": c.corner_id, "corner_type": c.corner_type,
             "apex_distance_m": c.apex_distance_m, "start_distance_m": c.start_distance_m,
             "end_distance_m": c.end_distance_m, "label": kc.number,
             "name": kc.name, "description": kc.description}
            for c, kc in zip(corners, known_corners)
        ]
    corner_list = [
        {"corner_id": c.corner_id, "corner_type": c.corner_type, "apex_distance_m": c.apex_distance_m,
         "start_distance_m": c.start_distance_m, "end_distance_m": c.end_distance_m}
        for c in corners
    ]
    return map_detected_to_known(corner_list, known)


def _build_corner_suggestions(parsed, laps, corners, known):
    """Compute data-driven corner improvement suggestions.

    Anchors everything on the best lap vs the session-best at each corner,
    so estimated gains are realistic and sum roughly to the theoretical best delta.
    """
    flying = filter_flying_laps(laps)
    if not corners or not flying:
        return {"suggestions": [], "summary": "No corners detected.", "total_estimated_gain_s": 0, "num_corners": 0, "track_name": "Unknown"}

    best_lap = min(flying, key=lambda l: l["lap_time_s"])
    best_lap_num = best_lap["lap_number"]

    corner_names = _build_name_map(corners, known)

    def _label(cid): return corner_names.get(cid, f"Turn {cid}")
    def _mph(kph): return kph * KPH_TO_MPH

    suggestions = []
    total_corner_delta = 0.0

    for corner in corners:
        corner_data_all = []
        best_lap_data = None
        for lap in flying:
            lap_df = segment_lap_distance(parsed.df, lap["start_time_ms"], lap["end_time_ms"])
            analysis = analyze_corner_for_lap(lap_df, corner)
            if analysis:
                analysis.lap_number = lap["lap_number"]
                corner_data_all.append(analysis)
                if lap["lap_number"] == best_lap_num:
                    best_lap_data = analysis
        if len(corner_data_all) < 2 or best_lap_data is None:
            continue

        session_best = min(corner_data_all, key=lambda x: x.time_in_corner_s)
        corner_delta = best_lap_data.time_in_corner_s - session_best.time_in_corner_s
        if corner_delta < 0.01:
            continue

        total_corner_delta += corner_delta
        direction = "left" if corner.corner_type == "left" else "right"
        label = _label(corner.corner_id)

        corner_suggestions = []

        if best_lap_data.braking_start_distance_m is not None and session_best.braking_start_distance_m is not None:
            brake_diff = session_best.braking_start_distance_m - best_lap_data.braking_start_distance_m
            if brake_diff > 5:
                brake_diff_ft = brake_diff * 3.281
                corner_suggestions.append({
                    "corner_id": corner.corner_id, "corner_label": label, "category": "braking",
                    "priority": "HIGH" if brake_diff > 15 else "MEDIUM",
                    "suggestion": f"Brake {brake_diff_ft:.0f} ft later at {label}. On Lap {session_best.lap_number} you braked later and were {corner_delta:.2f}s faster.",
                    "data": {"best_brake_ft": round(session_best.braking_start_distance_m * 3.281, 1), "your_brake_ft": round(best_lap_data.braking_start_distance_m * 3.281, 1), "delta_ft": round(brake_diff_ft, 1)},
                })

        entry_diff = _mph(session_best.entry_speed_kph) - _mph(best_lap_data.entry_speed_kph)
        if entry_diff > 2:
            corner_suggestions.append({
                "corner_id": corner.corner_id, "corner_label": label, "category": "entry_speed",
                "priority": "HIGH" if entry_diff > 5 else "MEDIUM",
                "suggestion": f"Carry {entry_diff:.0f} mph more into {label} ({direction}). On Lap {session_best.lap_number} you entered at {_mph(session_best.entry_speed_kph):.0f} mph vs {_mph(best_lap_data.entry_speed_kph):.0f} mph on your best lap.",
                "data": {"target_entry_mph": round(_mph(session_best.entry_speed_kph), 1), "your_entry_mph": round(_mph(best_lap_data.entry_speed_kph), 1)},
            })

        apex_diff = _mph(session_best.min_speed_kph) - _mph(best_lap_data.min_speed_kph)
        if apex_diff > 2:
            corner_suggestions.append({
                "corner_id": corner.corner_id, "corner_label": label, "category": "apex_speed",
                "priority": "MEDIUM",
                "suggestion": f"Carry {apex_diff:.0f} mph more through the apex at {label}.",
                "data": {"target_apex_mph": round(_mph(session_best.min_speed_kph), 1), "your_apex_mph": round(_mph(best_lap_data.min_speed_kph), 1)},
            })

        exit_diff = _mph(session_best.exit_speed_kph) - _mph(best_lap_data.exit_speed_kph)
        if exit_diff > 2:
            corner_suggestions.append({
                "corner_id": corner.corner_id, "corner_label": label, "category": "exit_speed",
                "priority": "HIGH" if exit_diff > 5 else "MEDIUM",
                "suggestion": f"Get {exit_diff:.0f} mph more exit speed out of {label}.",
                "data": {"target_exit_mph": round(_mph(session_best.exit_speed_kph), 1), "your_exit_mph": round(_mph(best_lap_data.exit_speed_kph), 1)},
            })

        # Split the corner's actual time delta across its suggestions
        n = len(corner_suggestions)
        if n > 0:
            share = round(corner_delta / n, 2)
            for s in corner_suggestions:
                s["estimated_gain_s"] = share
            suggestions.extend(corner_suggestions)

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    suggestions.sort(key=lambda s: (priority_order.get(s["priority"], 2), -(s.get("estimated_gain_s") or 0)))
    total_gain = round(total_corner_delta, 2)
    track_name = known["full_name"] if known else "this session"

    return {
        "suggestions": suggestions,
        "total_estimated_gain_s": total_gain,
        "num_corners": len(corners),
        "track_name": track_name,
        "summary": f"Found {len(suggestions)} improvement opportunities across {len(corners)} corners at {track_name}.",
    }


# ---------------------------------------------------------------------------
# POST /api/analyze  — main upload + analysis endpoint
# ---------------------------------------------------------------------------

@router.post("")
async def analyze_file(file: UploadFile = File(...)):
    """Upload a telemetry file, parse it, and return full analysis.

    Returns a token for follow-up queries (speed traces, coaching, chat).
    """
    from pathlib import Path as _P
    ext = _P(file.filename or "unknown").suffix.lower()
    if ext not in (".xrk", ".xrz", ".csv"):
        raise HTTPException(400, f"Unsupported file type: {ext}. Use .xrk, .xrz, or .csv")

    content = await file.read()
    try:
        parsed = parse_file_bytes(file.filename or "unknown", content)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {e}")

    all_laps = parsed.laps
    # Drop lap 0 (out-lap) and the last lap (often an incomplete in-lap)
    laps = [l for l in all_laps if l["lap_number"] != 0]
    if len(laps) > 1:
        laps = laps[:-1]
    best_lap = min(laps, key=lambda l: l["lap_time_s"]) if laps else None

    # Track matching (before corner detection so we can use DB corners)
    known = _match_track_with_parsed(parsed)
    track_name = (
        known["full_name"] if known
        else parsed.metadata.get("Venue") or parsed.metadata.get("venue") or parsed.metadata.get("Track") or None
    )
    if not track_name:
        if known:
            track_name = known["full_name"]

    # Detect corners: use known track database when available, else auto-detect
    corners: list[DetectedCorner] = []
    if best_lap:
        best_df = segment_lap_distance(parsed.df, best_lap["start_time_ms"], best_lap["end_time_ms"])
        if known:
            corners = corners_from_known_track(known, best_df)
        if not corners:
            corners = detect_corners(best_df)

    # Cache parsed data for follow-up queries
    token = str(uuid.uuid4())
    _cache_put(token, parsed, laps, corners)

    # Lap summaries
    best_time = min(l["lap_time_s"] for l in laps) if laps else 0
    lap_summaries = []
    for lap in laps:
        summary = compute_lap_summary(parsed.df, lap)
        lap_summaries.append({
            "lap_number": lap["lap_number"],
            "lap_time_s": lap["lap_time_s"],
            "delta_to_best_s": round(lap["lap_time_s"] - best_time, 3),
            "max_speed_kph": summary.get("max_speed_kph"),
            "avg_lateral_g": summary.get("avg_lateral_g"),
            "max_lateral_g": summary.get("max_lateral_g"),
            "max_braking_g": summary.get("max_braking_g"),
        })

    # Theoretical best
    theoretical = compute_theoretical_best(parsed.df, laps, corners) if laps and corners else None
    if theoretical and theoretical.get("segment_sources"):
        name_map = _build_name_map(corners, known)
        for seg in theoretical["segment_sources"]:
            if seg.get("corner_id") and seg["corner_id"] in name_map:
                seg["label"] = name_map[seg["corner_id"]]

    # Consistency
    consistency = compute_consistency(parsed.df, laps, corners) if len(laps) > 1 and corners else None

    # Corner suggestions
    corner_suggestions = _build_corner_suggestions(parsed, laps, corners, known) if corners else None

    # Track info
    mapped_corners = _build_corner_info(corners, known)
    if known:
        track_info = {"track_name": known["full_name"], "track_matched": True, "corners": mapped_corners}
    else:
        track_info = {
            "track_name": track_name or "Unknown Track", "track_matched": False,
            "corners": mapped_corners,
        }

    # Session date
    file_meta = parsed.metadata
    session_date_str = file_meta.get("Log Date") or file_meta.get("Date")
    session_date = None
    if session_date_str:
        from datetime import datetime
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                session_date = datetime.strptime(session_date_str, fmt).isoformat()
                break
            except ValueError:
                continue

    # Weather data from Open-Meteo
    gps_lat = parsed.metadata.get("gps_lat") if parsed.metadata else None
    gps_lon = parsed.metadata.get("gps_lon") if parsed.metadata else None
    if gps_lat is None and "gps_lat" in parsed.df.columns:
        lat_vals = parsed.df["gps_lat"].dropna()
        if len(lat_vals) > 0:
            gps_lat = float(lat_vals.median())
            gps_lon = float(parsed.df["gps_lon"].dropna().median())

    session_hour = None
    log_time_str = file_meta.get("Log Time") or file_meta.get("Time")
    if log_time_str:
        try:
            session_hour = int(log_time_str.split(":")[0])
        except (ValueError, IndexError):
            pass

    weather = None
    if gps_lat is not None and gps_lon is not None:
        try:
            weather = await fetch_session_weather(
                latitude=gps_lat,
                longitude=gps_lon,
                session_date=session_date or session_date_str,
                session_hour=session_hour,
            )
        except Exception:
            pass  # weather is optional, don't fail the analysis

    # Update cache with weather data
    _cache_put(token, parsed, laps, corners, weather)

    return {
        "token": token,
        "filename": file.filename,
        "track_name": track_name,
        "session_date": session_date,
        "device_model": file_meta.get("Logger Model") or file_meta.get("Device Name"),
        "num_laps": len(laps),
        "best_lap_time_s": best_lap["lap_time_s"] if best_lap else None,
        "best_lap_number": best_lap["lap_number"] if best_lap else None,
        "channels_available": parsed.channels,
        "laps": lap_summaries,
        "theoretical_best": theoretical,
        "consistency": consistency,
        "corner_suggestions": corner_suggestions,
        "track_info": track_info,
        "weather": weather,
    }


# ---------------------------------------------------------------------------
# Clear session
# ---------------------------------------------------------------------------

@router.delete("/{token}")
async def clear_session(token: str):
    """Remove a cached analysis session so the user can start fresh."""
    removed = _cache.pop(token, None)
    return {"cleared": removed is not None, "token": token}


# ---------------------------------------------------------------------------
# Cross-file comparison (must be defined before {token} routes)
# ---------------------------------------------------------------------------

@router.get("/compare-cross")
async def cross_compare(
    token_a: str = Query(...), lap_a: int = Query(...),
    token_b: str = Query(...), lap_b: int = Query(...),
):
    """Compare laps from two different uploaded files."""
    parsed_a, laps_a, corners_a = _cache_get(token_a)
    parsed_b, laps_b, corners_b = _cache_get(token_b)

    lap_a_data = next((l for l in laps_a if l["lap_number"] == lap_a), None)
    lap_b_data = next((l for l in laps_b if l["lap_number"] == lap_b), None)
    if not lap_a_data:
        raise HTTPException(404, f"Lap {lap_a} not found in file A")
    if not lap_b_data:
        raise HTTPException(404, f"Lap {lap_b} not found in file B")

    result = compare_laps(parsed_a.df, lap_a_data, lap_b_data, corners_a, df_b_override=parsed_b.df)

    known_a = _match_track_with_parsed(parsed_a)
    name_map = _build_name_map(corners_a, known_a)
    for cd in result.get("corner_deltas", []):
        cd["corner_label"] = name_map.get(cd["corner_id"], f"Turn {cd['corner_id']}")

    return result


@router.post("/compare-cross/coaching")
async def cross_compare_coaching(
    token_a: str = Query(...), lap_a: int = Query(...),
    token_b: str = Query(...), lap_b: int = Query(...),
    x_openai_key: str | None = Header(None),
    x_ai_provider: str | None = Header(None),
    x_ai_model: str | None = Header(None),
):
    """AI coaching for cross-file lap comparison."""
    parsed_a, laps_a, corners_a = _cache_get(token_a)
    parsed_b, laps_b, _ = _cache_get(token_b)

    lap_a_data = next((l for l in laps_a if l["lap_number"] == lap_a), None)
    lap_b_data = next((l for l in laps_b if l["lap_number"] == lap_b), None)
    if not lap_a_data or not lap_b_data:
        raise HTTPException(404, "Lap not found")

    result = compare_laps(parsed_a.df, lap_a_data, lap_b_data, corners_a, df_b_override=parsed_b.df)

    known_a = _match_track_with_parsed(parsed_a)
    name_map = _build_name_map(corners_a, known_a)
    for cd in result.get("corner_deltas", []):
        cd["corner_label"] = name_map.get(cd["corner_id"], f"Turn {cd['corner_id']}")

    adv_a = _convert_result_to_mph(compute_advanced_lap_metrics(parsed_a.df, lap_a_data, corners_a))
    adv_b = _convert_result_to_mph(compute_advanced_lap_metrics(parsed_b.df, lap_b_data, corners_a))
    result["advanced_metrics_lap_a"] = adv_a
    result["advanced_metrics_lap_b"] = adv_b

    return await generate_comparison_coaching(
        result,
        api_key=x_openai_key or None,
        provider=x_ai_provider or "openai",
        model=x_ai_model or "gpt-5.4",
    )


# ---------------------------------------------------------------------------
# Follow-up endpoints using cached token
# ---------------------------------------------------------------------------

@router.get("/{token}/speed-trace")
async def speed_trace(token: str, lap_numbers: str = Query(...)):
    parsed, laps, _ = _cache_get(token)
    requested = [int(n.strip()) for n in lap_numbers.split(",")]
    traces = {}
    for lap in laps:
        if lap["lap_number"] in requested:
            traces[lap["lap_number"]] = get_speed_trace(parsed.df, lap)
    return traces


@router.get("/{token}/gg-diagram")
async def gg_diagram(token: str, lap_number: int = Query(...)):
    parsed, laps, _ = _cache_get(token)
    lap = next((l for l in laps if l["lap_number"] == lap_number), None)
    if not lap:
        raise HTTPException(404, f"Lap {lap_number} not found")
    return compute_gg_data(parsed.df, lap)


@router.get("/{token}/compare")
async def compare_two_laps(token: str, lap_a: int = Query(...), lap_b: int = Query(...)):
    parsed, laps, corners = _cache_get(token)
    lap_a_data = next((l for l in laps if l["lap_number"] == lap_a), None)
    lap_b_data = next((l for l in laps if l["lap_number"] == lap_b), None)
    if not lap_a_data:
        raise HTTPException(404, f"Lap {lap_a} not found")
    if not lap_b_data:
        raise HTTPException(404, f"Lap {lap_b} not found")

    result = compare_laps(parsed.df, lap_a_data, lap_b_data, corners)

    known = _match_track_with_parsed(parsed)
    name_map = _build_name_map(corners, known)
    for cd in result.get("corner_deltas", []):
        cd["corner_label"] = name_map.get(cd["corner_id"], f"Turn {cd['corner_id']}")

    return result


@router.post("/{token}/compare/coaching")
async def compare_coaching(
    token: str, lap_a: int = Query(...), lap_b: int = Query(...),
    x_openai_key: str | None = Header(None),
    x_ai_provider: str | None = Header(None),
    x_ai_model: str | None = Header(None),
):
    parsed, laps, corners = _cache_get(token)
    lap_a_data = next((l for l in laps if l["lap_number"] == lap_a), None)
    lap_b_data = next((l for l in laps if l["lap_number"] == lap_b), None)
    if not lap_a_data or not lap_b_data:
        raise HTTPException(404, "Lap not found")

    result = compare_laps(parsed.df, lap_a_data, lap_b_data, corners)

    known = _match_track_with_parsed(parsed)
    name_map = _build_name_map(corners, known)
    for cd in result.get("corner_deltas", []):
        cd["corner_label"] = name_map.get(cd["corner_id"], f"Turn {cd['corner_id']}")

    adv_a = _convert_result_to_mph(compute_advanced_lap_metrics(parsed.df, lap_a_data, corners))
    adv_b = _convert_result_to_mph(compute_advanced_lap_metrics(parsed.df, lap_b_data, corners))
    result["advanced_metrics_lap_a"] = adv_a
    result["advanced_metrics_lap_b"] = adv_b

    return await generate_comparison_coaching(
        result,
        api_key=x_openai_key or None,
        provider=x_ai_provider or "openai",
        model=x_ai_model or "gpt-5.4",
    )


@router.get("/{token}/track-map")
async def track_map(token: str, lap_number: int = Query(...)):
    parsed, laps, corners = _cache_get(token)
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
            "lat": float(lat[i]), "lon": float(lon[i]),
            "speed_mph": round(float(speed_mph[i]), 1),
            "distance_m": round(float(distance[i]), 1),
            "time_ms": int(time_ms[i]),
        })

    known = _match_track_with_parsed(parsed)
    label_map = _build_label_map(corners, known)
    name_map = _build_name_map(corners, known)

    corner_markers = []
    for c in corners:
        apex_mask = np.abs(distance - c.apex_distance_m)
        apex_idx = int(np.argmin(apex_mask))
        if apex_idx < len(lat):
            corner_markers.append({
                "corner_id": c.corner_id, "corner_type": c.corner_type,
                "lat": float(lat[apex_idx]), "lon": float(lon[apex_idx]),
                "apex_distance_m": c.apex_distance_m,
                "label": label_map.get(c.corner_id, str(c.corner_id)),
                "name": name_map.get(c.corner_id, f"Turn {c.corner_id}"),
            })

    return {
        "points": points, "corners": corner_markers,
        "min_speed": round(float(np.nanmin(speed_mph)), 1),
        "max_speed": round(float(np.nanmax(speed_mph)), 1),
    }


@router.get("/{token}/braking-zones")
async def braking_zones(token: str, lap_number: int = Query(...)):
    parsed, laps, corners = _cache_get(token)
    lap = next((l for l in laps if l["lap_number"] == lap_number), None)
    if not lap:
        raise HTTPException(404, f"Lap {lap_number} not found")
    return get_braking_zones(parsed.df, lap, corners)


@router.get("/{token}/advanced-metrics")
async def advanced_metrics(token: str, lap_number: int = Query(...)):
    parsed, laps, corners = _cache_get(token)
    lap = next((l for l in laps if l["lap_number"] == lap_number), None)
    if not lap:
        raise HTTPException(404, f"Lap {lap_number} not found")
    return compute_advanced_lap_metrics(parsed.df, lap, corners)


# ---------------------------------------------------------------------------
# AI Coaching
# ---------------------------------------------------------------------------

@router.post("/{token}/coaching-report")
async def coaching_report(
    token: str,
    x_openai_key: str | None = Header(None),
    x_ai_provider: str | None = Header(None),
    x_ai_model: str | None = Header(None),
):
    parsed, laps, corners = _cache_get(token)
    known = _match_track_with_parsed(parsed)
    track_name = known["full_name"] if known else parsed.metadata.get("Venue") or "Unknown"

    theoretical = compute_theoretical_best(parsed.df, laps, corners) if laps and corners else None

    # Enrich theoretical best labels with track DB names
    if theoretical and theoretical.get("segment_sources"):
        name_map = _build_name_map(corners, known)
        for seg in theoretical["segment_sources"]:
            if seg.get("corner_id") and seg["corner_id"] in name_map:
                seg["label"] = name_map[seg["corner_id"]]

    consistency = compute_consistency(parsed.df, laps, corners) if len(laps) > 1 and corners else None

    best_lap = min(laps, key=lambda l: l["lap_time_s"]) if laps else None
    advanced = compute_advanced_lap_metrics(parsed.df, best_lap, corners) if best_lap else None

    # Build sector-by-sector comparison: best lap vs theoretical best
    sector_comparison = []
    if theoretical and theoretical.get("segment_sources") and best_lap:
        best_lap_num = best_lap["lap_number"]
        for seg in theoretical["segment_sources"]:
            best_lap_time_in_sector = seg.get("per_lap_times", {}).get(best_lap_num)
            time_lost = None
            if best_lap_time_in_sector is not None:
                time_lost = round(best_lap_time_in_sector - seg["best_time_s"], 3)
            sector_comparison.append({
                "sector_label": seg.get("label", "Unknown"),
                "theoretical_best_s": seg["best_time_s"],
                "from_lap": seg["from_lap"],
                "best_lap_time_s": best_lap_time_in_sector,
                "time_lost_s": time_lost,
            })

    # Corner suggestions (same data the frontend shows)
    corner_suggestions = _build_corner_suggestions(parsed, laps, corners, known) if corners else None

    # Filter to flying laps only for summaries
    flying_laps = filter_flying_laps(laps)

    weather = _cache_get_weather(token)

    summary_data = {
        "track": track_name,
        "num_laps": len(laps),
        "num_flying_laps": len(flying_laps),
        "best_lap_time_s": best_lap["lap_time_s"] if best_lap else None,
        "best_lap_number": best_lap["lap_number"] if best_lap else None,
        "channels": parsed.channels,
        "metadata": parsed.metadata or {},
        "theoretical_best": theoretical,
        "sector_comparison": sector_comparison,
        "corner_suggestions": corner_suggestions,
        "consistency": consistency,
        "lap_summaries": [_convert_result_to_mph(compute_lap_summary(parsed.df, lap)) for lap in flying_laps],
        "advanced_metrics_best_lap": _convert_result_to_mph(advanced) if advanced else None,
        "weather": weather,
    }

    return await generate_coaching_report(
        summary_data,
        api_key=x_openai_key or None,
        provider=x_ai_provider or "openai",
        model=x_ai_model or "gpt-5.4",
    )


@router.post("/{token}/chat")
async def chat(
    token: str,
    request: dict,
    x_openai_key: str | None = Header(None),
    x_ai_provider: str | None = Header(None),
    x_ai_model: str | None = Header(None),
):
    parsed, laps, corners = _cache_get(token)
    known = _match_track_with_parsed(parsed)
    track_name = known["full_name"] if known else parsed.metadata.get("Venue") or "Unknown"

    best_lap = min(laps, key=lambda l: l["lap_time_s"]) if laps else None
    context = {
        "track": track_name,
        "device": parsed.metadata.get("Logger Model") or parsed.metadata.get("Device Name") or "Unknown",
        "date": parsed.metadata.get("Log Date") or parsed.metadata.get("Date") or "Unknown",
        "num_laps": len(laps),
        "best_lap_time_s": best_lap["lap_time_s"] if best_lap else None,
        "best_lap_number": best_lap["lap_number"] if best_lap else None,
        "channels": parsed.channels,
        "metadata": parsed.metadata or {},
        "lap_times": [{"lap": l["lap_number"], "time_s": l["lap_time_s"]} for l in laps],
    }

    async def executor(fn_name: str, fn_args: dict) -> dict:
        if fn_name == "get_session_summary":
            return context

        elif fn_name == "get_lap_comparison":
            la = next((l for l in laps if l["lap_number"] == fn_args["lap_a"]), None)
            lb = next((l for l in laps if l["lap_number"] == fn_args["lap_b"]), None)
            if not la or not lb:
                return {"error": "Lap not found"}
            comparison = {"lap_a": la, "lap_b": lb, "corners": []}
            for corner in corners:
                df_a = segment_lap_distance(parsed.df, la["start_time_ms"], la["end_time_ms"])
                df_b = segment_lap_distance(parsed.df, lb["start_time_ms"], lb["end_time_ms"])
                ca = analyze_corner_for_lap(df_a, corner)
                cb = analyze_corner_for_lap(df_b, corner)
                if ca and cb:
                    ca.lap_number = fn_args["lap_a"]
                    cb.lap_number = fn_args["lap_b"]
                    comparison["corners"].append({
                        "corner_id": corner.corner_id, "corner_type": corner.corner_type,
                        "lap_a": _corner_data_to_mph(ca.__dict__),
                        "lap_b": _corner_data_to_mph(cb.__dict__),
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
                        results.append(_corner_data_to_mph(a.__dict__))
            return {"corner_id": cid, "data": results}

        elif fn_name == "get_speed_trace":
            traces = {}
            for lap in laps:
                if lap["lap_number"] in fn_args["lap_numbers"]:
                    trace = get_speed_trace(parsed.df, lap)
                    if "speed_kph" in trace:
                        trace["speed_mph"] = [round(v * KPH_TO_MPH, 1) for v in trace.pop("speed_kph")]
                    traces[str(lap["lap_number"])] = trace
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
            return parsed.metadata.get("weather", {})

        elif fn_name == "get_tire_condition":
            return {"tires": []}

        elif fn_name == "get_car_setup":
            return {"setup_metadata": {}, "photo_analysis": []}

        elif fn_name == "get_gg_diagram":
            ln = fn_args["lap_number"]
            lap = next((l for l in laps if l["lap_number"] == ln), None)
            if not lap:
                return {"error": f"Lap {ln} not found"}
            gg = compute_gg_data(parsed.df, lap)
            if gg.get("speed_kph"):
                gg["speed_mph"] = [round(v * KPH_TO_MPH, 1) for v in gg.pop("speed_kph")]
            return gg

        elif fn_name == "get_advanced_corner_analysis":
            ln = fn_args["lap_number"]
            lap = next((l for l in laps if l["lap_number"] == ln), None)
            if not lap:
                return {"error": f"Lap {ln} not found"}
            adv_result = compute_advanced_lap_metrics(parsed.df, lap, corners)
            cid = fn_args.get("corner_id")
            if cid is not None:
                filtered = [c for c in adv_result["corners"] if c["corner_id"] == cid]
                adv_result["corners"] = filtered
            return _convert_result_to_mph(adv_result)

        return {"error": f"Unknown function: {fn_name}"}

    user_message = request.get("message", "")
    history = request.get("conversation_history", [])

    result = await chat_with_coach(
        session_id=token,
        user_message=user_message,
        conversation_history=history,
        session_context=context,
        tool_executor=executor,
        api_key=x_openai_key or None,
        provider=x_ai_provider or "openai",
        model=x_ai_model or "gpt-5.4",
    )

    return {"message": result["message"], "tool_calls_made": result.get("tool_calls_made", [])}
