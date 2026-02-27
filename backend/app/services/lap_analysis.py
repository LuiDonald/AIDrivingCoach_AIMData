"""Lap analysis engine: theoretical best, corner deltas, consistency, g-g diagram."""

import numpy as np
import pandas as pd
from dataclasses import dataclass

from app.services.track_segmentation import DetectedCorner, segment_lap_distance


@dataclass
class CornerLapData:
    corner_id: int
    lap_number: int
    entry_speed_kph: float
    min_speed_kph: float
    exit_speed_kph: float
    max_lateral_g: float
    time_in_corner_s: float
    braking_start_distance_m: float | None = None
    throttle_start_distance_m: float | None = None


def analyze_corner_for_lap(
    lap_df: pd.DataFrame, corner: DetectedCorner
) -> CornerLapData | None:
    """Analyze a single corner for a single lap."""
    mask = (
        (lap_df["distance_m"] >= corner.start_distance_m)
        & (lap_df["distance_m"] <= corner.end_distance_m)
    )
    corner_data = lap_df[mask]

    if len(corner_data) < 5:
        return None

    speed = corner_data["speed_kph"].values if "speed_kph" in corner_data else None
    if speed is None or len(speed) == 0:
        return None

    entry_speed = float(speed[0])
    min_speed = float(np.min(speed))
    exit_speed = float(speed[-1])

    lat_g = corner_data["lateral_g"].values if "lateral_g" in corner_data else np.zeros(len(corner_data))
    max_lat_g = float(np.max(np.abs(lat_g)))

    time_range = corner_data["time_ms"].values
    time_in_corner = (time_range[-1] - time_range[0]) / 1000.0

    braking_start = None
    if "longitudinal_g" in corner_data.columns:
        lon_g = corner_data["longitudinal_g"].values
        braking_mask = lon_g < -0.2
        if np.any(braking_mask):
            first_brake_idx = np.argmax(braking_mask)
            braking_start = float(corner_data["distance_m"].values[first_brake_idx])

    throttle_start = None
    if "throttle_pct" in corner_data.columns:
        throttle = corner_data["throttle_pct"].values
        min_speed_idx = np.argmin(speed)
        after_apex = throttle[min_speed_idx:]
        throttle_on = after_apex > 20
        if np.any(throttle_on):
            t_idx = min_speed_idx + np.argmax(throttle_on)
            throttle_start = float(corner_data["distance_m"].values[t_idx])

    return CornerLapData(
        corner_id=corner.corner_id,
        lap_number=0,
        entry_speed_kph=round(entry_speed, 1),
        min_speed_kph=round(min_speed, 1),
        exit_speed_kph=round(exit_speed, 1),
        max_lateral_g=round(max_lat_g, 3),
        time_in_corner_s=round(time_in_corner, 3),
        braking_start_distance_m=round(braking_start, 1) if braking_start else None,
        throttle_start_distance_m=round(throttle_start, 1) if throttle_start else None,
    )


def compute_theoretical_best(
    df: pd.DataFrame,
    laps: list[dict],
    corners: list[DetectedCorner],
) -> dict:
    """Compute theoretical best lap from fastest segments across all laps.

    Divides the track into segments (between corners) and takes the fastest
    time through each segment across all laps.
    """
    if len(laps) < 2 or len(corners) == 0:
        best_lap = min(laps, key=lambda l: l["lap_time_s"]) if laps else None
        return {
            "actual_best_time_s": best_lap["lap_time_s"] if best_lap else 0,
            "theoretical_best_time_s": best_lap["lap_time_s"] if best_lap else 0,
            "time_delta_s": 0,
            "improvement_pct": 0,
            "segment_sources": [],
        }

    ref_lap = min(laps, key=lambda l: l["lap_time_s"])
    ref_df = segment_lap_distance(df, ref_lap["start_time_ms"], ref_lap["end_time_ms"])
    if len(ref_df) == 0:
        return {
            "actual_best_time_s": ref_lap["lap_time_s"],
            "theoretical_best_time_s": ref_lap["lap_time_s"],
            "time_delta_s": 0,
            "improvement_pct": 0,
            "segment_sources": [],
        }

    total_dist = ref_df["distance_m"].max()

    breakpoints = [0.0]
    for c in corners:
        breakpoints.append(c.start_distance_m)
        breakpoints.append(c.end_distance_m)
    breakpoints.append(total_dist)
    breakpoints = sorted(set(breakpoints))

    segments = []
    for i in range(len(breakpoints) - 1):
        if breakpoints[i + 1] - breakpoints[i] > 5:
            segments.append((breakpoints[i], breakpoints[i + 1]))

    best_segment_times = []
    for seg_start, seg_end in segments:
        best_time = float("inf")
        best_source = -1

        for lap in laps:
            lap_df = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])
            if len(lap_df) == 0:
                continue

            mask = (lap_df["distance_m"] >= seg_start) & (lap_df["distance_m"] <= seg_end)
            seg_data = lap_df[mask]
            if len(seg_data) < 2:
                continue

            seg_time = (seg_data["time_ms"].iloc[-1] - seg_data["time_ms"].iloc[0]) / 1000.0
            if seg_time < best_time:
                best_time = seg_time
                best_source = lap["lap_number"]

        if best_time < float("inf"):
            best_segment_times.append({
                "segment_start_m": seg_start,
                "segment_end_m": seg_end,
                "best_time_s": round(best_time, 3),
                "from_lap": best_source,
            })

    theoretical = sum(s["best_time_s"] for s in best_segment_times)
    actual_best = ref_lap["lap_time_s"]
    delta = actual_best - theoretical
    improvement_pct = (delta / actual_best * 100) if actual_best > 0 else 0

    return {
        "actual_best_time_s": round(actual_best, 3),
        "theoretical_best_time_s": round(theoretical, 3),
        "time_delta_s": round(delta, 3),
        "improvement_pct": round(improvement_pct, 2),
        "segment_sources": best_segment_times,
    }


def compute_consistency(
    df: pd.DataFrame,
    laps: list[dict],
    corners: list[DetectedCorner],
) -> dict:
    """Score driver consistency across laps and corners."""
    if len(laps) < 3:
        return {
            "overall_score_pct": 0,
            "lap_time_std_s": 0,
            "corner_scores": [],
            "most_consistent_corners": [],
            "least_consistent_corners": [],
        }

    lap_times = [l["lap_time_s"] for l in laps]
    median_time = np.median(lap_times)
    valid_laps = [l for l in laps if l["lap_time_s"] < median_time * 1.1]
    if len(valid_laps) < 3:
        valid_laps = laps

    valid_times = [l["lap_time_s"] for l in valid_laps]
    lap_std = float(np.std(valid_times))

    corner_scores = []
    for corner in corners:
        corner_times = []
        for lap in valid_laps:
            lap_df = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])
            result = analyze_corner_for_lap(lap_df, corner)
            if result:
                corner_times.append(result.time_in_corner_s)

        if len(corner_times) >= 3:
            std = float(np.std(corner_times))
            mean = float(np.mean(corner_times))
            cv = (std / mean * 100) if mean > 0 else 0
            score = max(0, 100 - cv * 20)
            corner_scores.append({
                "corner_id": corner.corner_id,
                "consistency_score": round(score, 1),
                "std_s": round(std, 3),
                "mean_time_s": round(mean, 3),
            })

    if corner_scores:
        overall = float(np.mean([c["consistency_score"] for c in corner_scores]))
    else:
        max_time = max(valid_times)
        min_time = min(valid_times)
        spread_pct = (max_time - min_time) / min_time * 100
        overall = max(0, 100 - spread_pct * 10)

    sorted_corners = sorted(corner_scores, key=lambda c: c["consistency_score"], reverse=True)
    most_consistent = [c["corner_id"] for c in sorted_corners[:3]]
    least_consistent = [c["corner_id"] for c in sorted_corners[-3:]]

    return {
        "overall_score_pct": round(overall, 1),
        "lap_time_std_s": round(lap_std, 3),
        "corner_scores": corner_scores,
        "most_consistent_corners": most_consistent,
        "least_consistent_corners": least_consistent,
    }


def compute_gg_data(df: pd.DataFrame, lap: dict | None = None) -> dict:
    """Extract lateral vs longitudinal g for g-g diagram."""
    if lap:
        data = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])
    else:
        data = df

    result = {"lateral_g": [], "longitudinal_g": [], "speed_kph": None}

    if "lateral_g" in data.columns:
        result["lateral_g"] = data["lateral_g"].dropna().tolist()
    if "longitudinal_g" in data.columns:
        result["longitudinal_g"] = data["longitudinal_g"].dropna().tolist()

    min_len = min(len(result["lateral_g"]), len(result["longitudinal_g"]))
    result["lateral_g"] = result["lateral_g"][:min_len]
    result["longitudinal_g"] = result["longitudinal_g"][:min_len]

    if "speed_kph" in data.columns:
        speeds = data["speed_kph"].dropna().tolist()
        result["speed_kph"] = speeds[:min_len]

    return result


def compute_lap_summary(df: pd.DataFrame, lap: dict) -> dict:
    """Compute summary statistics for a single lap."""
    lap_df = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])

    summary = {
        "lap_number": lap["lap_number"],
        "lap_time_s": lap["lap_time_s"],
        "max_speed_kph": None,
        "avg_lateral_g": None,
        "max_lateral_g": None,
        "max_braking_g": None,
    }

    if "speed_kph" in lap_df.columns and len(lap_df) > 0:
        summary["max_speed_kph"] = round(float(lap_df["speed_kph"].max()), 1)

    if "lateral_g" in lap_df.columns and len(lap_df) > 0:
        abs_lat = lap_df["lateral_g"].abs()
        summary["avg_lateral_g"] = round(float(abs_lat.mean()), 3)
        summary["max_lateral_g"] = round(float(abs_lat.max()), 3)

    if "longitudinal_g" in lap_df.columns and len(lap_df) > 0:
        summary["max_braking_g"] = round(float(lap_df["longitudinal_g"].min()), 3)

    return summary


def get_speed_trace(df: pd.DataFrame, lap: dict) -> dict:
    """Get speed vs distance data for a lap."""
    lap_df = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])

    result = {"distance_m": [], "speed_kph": [], "time_ms": []}

    if len(lap_df) > 0:
        if "distance_m" in lap_df.columns:
            result["distance_m"] = lap_df["distance_m"].tolist()
        if "speed_kph" in lap_df.columns:
            result["speed_kph"] = lap_df["speed_kph"].tolist()
        result["time_ms"] = lap_df["time_ms"].tolist()

    return result


def compare_laps(
    df: pd.DataFrame,
    lap_a: dict,
    lap_b: dict,
    corners: list[DetectedCorner],
    df_b_override: pd.DataFrame | None = None,
) -> dict:
    """Compare two laps: time delta trace, speed diff, and corner-by-corner breakdown.

    lap_a is the reference (typically faster), lap_b is compared against it.
    Positive delta means lap_b is slower.
    If df_b_override is provided, lap_b data is read from that DataFrame instead
    (used for cross-session comparison).
    """
    df_a = segment_lap_distance(df, lap_a["start_time_ms"], lap_a["end_time_ms"])
    df_b = segment_lap_distance(
        df_b_override if df_b_override is not None else df,
        lap_b["start_time_ms"],
        lap_b["end_time_ms"],
    )

    if len(df_a) == 0 or len(df_b) == 0:
        return {"error": "No data for one or both laps"}

    KPH_TO_MPH = 0.621371

    max_dist = min(df_a["distance_m"].max(), df_b["distance_m"].max())
    sample_distances = np.linspace(0, max_dist, min(500, int(max_dist)))

    speed_a = np.interp(sample_distances, df_a["distance_m"].values, df_a["speed_kph"].values) * KPH_TO_MPH
    speed_b = np.interp(sample_distances, df_b["distance_m"].values, df_b["speed_kph"].values) * KPH_TO_MPH
    time_a = np.interp(sample_distances, df_a["distance_m"].values, df_a["time_ms"].values)
    time_b = np.interp(sample_distances, df_b["distance_m"].values, df_b["time_ms"].values)

    # Time delta: how much behind is lap_b at each distance point
    # Both traces start at time=0 at distance=0, so delta = time_b - time_a
    time_a_zeroed = time_a - time_a[0]
    time_b_zeroed = time_b - time_b[0]
    time_delta_ms = time_b_zeroed - time_a_zeroed
    speed_diff = speed_a - speed_b

    delta_trace = []
    step = max(1, len(sample_distances) // 500)
    for i in range(0, len(sample_distances), step):
        delta_trace.append({
            "distance_m": round(float(sample_distances[i]), 1),
            "time_delta_s": round(float(time_delta_ms[i]) / 1000.0, 3),
            "speed_a_mph": round(float(speed_a[i]), 1),
            "speed_b_mph": round(float(speed_b[i]), 1),
            "speed_diff_mph": round(float(speed_diff[i]), 1),
        })

    # Corner-by-corner comparison
    corner_deltas = []
    for corner in corners:
        ca = analyze_corner_for_lap(df_a, corner)
        cb = analyze_corner_for_lap(df_b, corner)
        if ca and cb:
            time_delta = cb.time_in_corner_s - ca.time_in_corner_s
            corner_deltas.append({
                "corner_id": corner.corner_id,
                "corner_type": corner.corner_type,
                "time_delta_s": round(time_delta, 3),
                "lap_a": {
                    "entry_speed_mph": round(ca.entry_speed_kph * KPH_TO_MPH, 1),
                    "min_speed_mph": round(ca.min_speed_kph * KPH_TO_MPH, 1),
                    "exit_speed_mph": round(ca.exit_speed_kph * KPH_TO_MPH, 1),
                    "time_s": round(ca.time_in_corner_s, 3),
                    "max_lateral_g": ca.max_lateral_g,
                },
                "lap_b": {
                    "entry_speed_mph": round(cb.entry_speed_kph * KPH_TO_MPH, 1),
                    "min_speed_mph": round(cb.min_speed_kph * KPH_TO_MPH, 1),
                    "exit_speed_mph": round(cb.exit_speed_kph * KPH_TO_MPH, 1),
                    "time_s": round(cb.time_in_corner_s, 3),
                    "max_lateral_g": cb.max_lateral_g,
                },
            })

    # Where are the biggest gains/losses
    biggest_loss = max(corner_deltas, key=lambda c: c["time_delta_s"]) if corner_deltas else None
    biggest_gain = min(corner_deltas, key=lambda c: c["time_delta_s"]) if corner_deltas else None

    return {
        "lap_a": lap_a["lap_number"],
        "lap_b": lap_b["lap_number"],
        "lap_a_time_s": lap_a["lap_time_s"],
        "lap_b_time_s": lap_b["lap_time_s"],
        "total_delta_s": round(lap_b["lap_time_s"] - lap_a["lap_time_s"], 3),
        "delta_trace": delta_trace,
        "corner_deltas": corner_deltas,
        "biggest_loss_corner": biggest_loss["corner_id"] if biggest_loss else None,
        "biggest_gain_corner": biggest_gain["corner_id"] if biggest_gain else None,
    }


def get_braking_zones(df: pd.DataFrame, lap: dict, corners: list[DetectedCorner]) -> list[dict]:
    """Extract braking zone data for each corner in a lap."""
    lap_df = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])
    zones = []

    for corner in corners:
        approach_start = max(0, corner.start_distance_m - 100)
        mask = (
            (lap_df["distance_m"] >= approach_start)
            & (lap_df["distance_m"] <= corner.apex_distance_m)
        )
        zone_data = lap_df[mask]

        if len(zone_data) < 3:
            continue

        zone = {
            "corner_id": corner.corner_id,
            "braking_start_m": None,
            "braking_end_m": None,
            "max_decel_g": None,
            "braking_duration_s": None,
        }

        if "longitudinal_g" in zone_data.columns:
            lon_g = zone_data["longitudinal_g"].values
            braking = lon_g < -0.2
            if np.any(braking):
                first_idx = np.argmax(braking)
                last_idx = len(braking) - 1 - np.argmax(braking[::-1])
                zone["braking_start_m"] = float(zone_data["distance_m"].values[first_idx])
                zone["braking_end_m"] = float(zone_data["distance_m"].values[last_idx])
                zone["max_decel_g"] = round(float(np.min(lon_g)), 3)
                zone["braking_duration_s"] = round(
                    (zone_data["time_ms"].values[last_idx] - zone_data["time_ms"].values[first_idx]) / 1000.0, 3
                )

        zones.append(zone)

    return zones
