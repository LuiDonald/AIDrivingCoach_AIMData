"""Lap analysis engine: theoretical best, corner deltas, consistency, g-g diagram."""

import numpy as np
import pandas as pd
from dataclasses import dataclass

from app.services.track_segmentation import DetectedCorner, segment_lap_distance

FLYING_LAP_THRESHOLD = 1.10


def filter_flying_laps(laps: list[dict]) -> list[dict]:
    """Return only representative flying laps (within 110% of the best).

    Excludes out-laps, in-laps, and any laps that are significantly off-pace.
    """
    if not laps:
        return laps
    best_time = min(l["lap_time_s"] for l in laps)
    cutoff = best_time * FLYING_LAP_THRESHOLD
    return [l for l in laps if l["lap_time_s"] <= cutoff]


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
    time through each segment across all flying laps (excludes out/in laps).
    """
    laps = filter_flying_laps(laps)
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

    # Build a map from (start, end) → corner for labeling
    corner_map: dict[tuple[float, float], DetectedCorner] = {}
    for c in corners:
        for seg_s, seg_e in segments:
            if abs(seg_s - c.start_distance_m) < 1 and abs(seg_e - c.end_distance_m) < 1:
                corner_map[(seg_s, seg_e)] = c
                break

    # Pre-compute lap DataFrames to avoid redundant parsing
    lap_dfs = {}
    for lap in laps:
        lap_df = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])
        if len(lap_df) > 0:
            lap_dfs[lap["lap_number"]] = lap_df

    best_segment_times = []
    for seg_start, seg_end in segments:
        best_time = float("inf")
        best_source = -1
        per_lap_times = {}

        for lap in laps:
            lap_df = lap_dfs.get(lap["lap_number"])
            if lap_df is None:
                continue

            mask = (lap_df["distance_m"] >= seg_start) & (lap_df["distance_m"] <= seg_end)
            seg_data = lap_df[mask]
            if len(seg_data) < 2:
                continue

            seg_time = (seg_data["time_ms"].iloc[-1] - seg_data["time_ms"].iloc[0]) / 1000.0
            per_lap_times[lap["lap_number"]] = round(seg_time, 3)
            if seg_time < best_time:
                best_time = seg_time
                best_source = lap["lap_number"]

        if best_time < float("inf"):
            corner = corner_map.get((seg_start, seg_end))
            seg_type = "corner" if corner else "straight"
            seg_label = f"Turn {corner.corner_id}" if corner else "Straight"
            best_segment_times.append({
                "segment_start_m": seg_start,
                "segment_end_m": seg_end,
                "best_time_s": round(best_time, 3),
                "from_lap": best_source,
                "type": seg_type,
                "label": seg_label,
                "corner_id": corner.corner_id if corner else None,
                "per_lap_times": per_lap_times,
            })

    # Merge each straight with the following corner into a single sector.
    # This gives drivers one sector per corner (approach + corner).
    merged = _merge_sectors(best_segment_times)

    theoretical = sum(s["best_time_s"] for s in merged)
    actual_best = ref_lap["lap_time_s"]
    delta = actual_best - theoretical
    improvement_pct = (delta / actual_best * 100) if actual_best > 0 else 0

    return {
        "actual_best_time_s": round(actual_best, 3),
        "theoretical_best_time_s": round(theoretical, 3),
        "time_delta_s": round(delta, 3),
        "improvement_pct": round(improvement_pct, 2),
        "best_lap_number": ref_lap["lap_number"],
        "segment_sources": merged,
    }


def _merge_sectors(segments: list[dict]) -> list[dict]:
    """Merge straight segments with the following corner into combined sectors.

    Each resulting sector contains the approach straight + the corner itself,
    giving drivers a natural per-corner view of the lap.
    """
    if not segments:
        return []

    merged: list[dict] = []
    pending_straight: dict | None = None

    for seg in segments:
        if seg["type"] == "straight":
            if pending_straight is not None:
                merged.append(pending_straight)
            pending_straight = seg
        else:
            if pending_straight is not None:
                merged.append(_combine_two(pending_straight, seg))
                pending_straight = None
            else:
                merged.append(seg)

    if pending_straight is not None:
        if merged:
            merged[-1] = _combine_two(merged[-1], pending_straight)
        else:
            merged.append(pending_straight)

    return merged


def _combine_two(a: dict, b: dict) -> dict:
    """Combine two adjacent segments into one, summing per-lap times."""
    all_laps = set(a.get("per_lap_times", {}).keys()) | set(b.get("per_lap_times", {}).keys())
    combined_per_lap = {}
    for lap in all_laps:
        t_a = a.get("per_lap_times", {}).get(lap)
        t_b = b.get("per_lap_times", {}).get(lap)
        if t_a is not None and t_b is not None:
            combined_per_lap[lap] = round(t_a + t_b, 3)

    best_time = float("inf")
    best_source = -1
    for lap, t in combined_per_lap.items():
        if t < best_time:
            best_time = t
            best_source = lap

    corner_seg = b if b["type"] == "corner" else a
    return {
        "segment_start_m": a["segment_start_m"],
        "segment_end_m": b["segment_end_m"],
        "best_time_s": round(best_time, 3) if best_time < float("inf") else round(a["best_time_s"] + b["best_time_s"], 3),
        "from_lap": best_source if best_source >= 0 else a["from_lap"],
        "type": "sector",
        "label": corner_seg["label"],
        "corner_id": corner_seg.get("corner_id"),
        "per_lap_times": combined_per_lap,
    }


def compute_consistency(
    df: pd.DataFrame,
    laps: list[dict],
    corners: list[DetectedCorner],
) -> dict:
    """Score driver consistency across flying laps and corners."""
    laps = filter_flying_laps(laps)
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

    # Interpolate optional input channels for overlay charts
    def _interp_channel(df_lap, col):
        if col in df_lap.columns:
            vals = df_lap[col].fillna(0).values
            return np.interp(sample_distances, df_lap["distance_m"].values, vals)
        return None

    throttle_a = _interp_channel(df_a, "throttle_pct")
    throttle_b = _interp_channel(df_b, "throttle_pct")
    brake_a = _interp_channel(df_a, "brake_pressure")
    brake_b = _interp_channel(df_b, "brake_pressure")
    steer_a = _interp_channel(df_a, "steering_angle")
    steer_b = _interp_channel(df_b, "steering_angle")

    # Time delta: how much behind is lap_b at each distance point
    # Both traces start at time=0 at distance=0, so delta = time_b - time_a
    time_a_zeroed = time_a - time_a[0]
    time_b_zeroed = time_b - time_b[0]
    time_delta_ms = time_b_zeroed - time_a_zeroed
    speed_diff = speed_a - speed_b

    delta_trace = []
    step = max(1, len(sample_distances) // 500)
    for i in range(0, len(sample_distances), step):
        pt: dict = {
            "distance_m": round(float(sample_distances[i]), 1),
            "time_delta_s": round(float(time_delta_ms[i]) / 1000.0, 3),
            "speed_a_mph": round(float(speed_a[i]), 1),
            "speed_b_mph": round(float(speed_b[i]), 1),
            "speed_diff_mph": round(float(speed_diff[i]), 1),
        }
        if throttle_a is not None:
            pt["throttle_a"] = round(float(throttle_a[i]), 1)
        if throttle_b is not None:
            pt["throttle_b"] = round(float(throttle_b[i]), 1)
        if brake_a is not None:
            pt["brake_a"] = round(float(brake_a[i]), 1)
        if brake_b is not None:
            pt["brake_b"] = round(float(brake_b[i]), 1)
        if steer_a is not None:
            pt["steer_a"] = round(float(steer_a[i]), 1)
        if steer_b is not None:
            pt["steer_b"] = round(float(steer_b[i]), 1)
        delta_trace.append(pt)

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

    available_channels = []
    if throttle_a is not None or throttle_b is not None:
        available_channels.append("throttle")
    if brake_a is not None or brake_b is not None:
        available_channels.append("brake")
    if steer_a is not None or steer_b is not None:
        available_channels.append("steering")

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
        "available_channels": available_channels,
    }


def compute_advanced_corner_metrics(
    lap_df: pd.DataFrame, corner: DetectedCorner
) -> dict | None:
    """Compute advanced per-corner metrics: friction circle, trail-braking, throttle, steering, wheel slip.

    Returns None if insufficient data. All metrics are optional — each is computed
    only if the required channels are present in the DataFrame.
    """
    mask = (
        (lap_df["distance_m"] >= corner.start_distance_m)
        & (lap_df["distance_m"] <= corner.end_distance_m)
    )
    cd = lap_df[mask]
    if len(cd) < 5 or "speed_kph" not in cd.columns:
        return None

    speed = cd["speed_kph"].values
    dist = cd["distance_m"].values
    time_ms = cd["time_ms"].values
    min_speed_idx = int(np.argmin(speed))

    result: dict = {"corner_id": corner.corner_id}

    # --- Friction circle utilization ---
    has_lat = "lateral_g" in cd.columns
    has_lon = "longitudinal_g" in cd.columns
    if has_lat and has_lon:
        lat_g = cd["lateral_g"].values
        lon_g = cd["longitudinal_g"].values
        g_mag = np.sqrt(lat_g**2 + lon_g**2)
        max_g = float(np.max(g_mag)) if len(g_mag) > 0 else 1.0
        if max_g > 0.05:
            pct_above_90 = float(np.mean(g_mag >= max_g * 0.9) * 100)
            avg_utilization = float(np.mean(g_mag) / max_g * 100)
        else:
            pct_above_90 = 0.0
            avg_utilization = 0.0
        result["friction_circle"] = {
            "max_g_magnitude": round(max_g, 3),
            "avg_g_utilization_pct": round(avg_utilization, 1),
            "pct_time_above_90_pct_grip": round(pct_above_90, 1),
        }

    # --- Trail-braking score ---
    has_brake = "brake_pressure" in cd.columns
    has_steer = "steering_angle" in cd.columns
    if has_brake and has_steer:
        brake = cd["brake_pressure"].values
        steer = np.abs(cd["steering_angle"].values)
        brake_max = float(np.max(brake)) if len(brake) > 0 else 1.0
        steer_max = float(np.max(steer)) if len(steer) > 0 else 1.0
        if brake_max > 0 and steer_max > 0:
            brake_norm = brake / brake_max
            steer_norm = steer / steer_max
            overlap = (brake_norm > 0.1) & (steer_norm > 0.1)
            overlap_pct = float(np.mean(overlap[:min_speed_idx + 1]) * 100) if min_speed_idx > 0 else 0.0
            # Brake release smoothness: std of derivative in the release phase
            entry_brake = brake[:min_speed_idx + 1]
            if len(entry_brake) > 3:
                dt = np.diff(time_ms[:min_speed_idx + 1]) / 1000.0
                dt[dt == 0] = 0.001
                brake_deriv = np.diff(entry_brake) / dt
                release_mask = brake_deriv < 0
                if np.any(release_mask):
                    release_smoothness = 100.0 - min(float(np.std(brake_deriv[release_mask])) * 2, 100.0)
                else:
                    release_smoothness = 50.0
            else:
                release_smoothness = 50.0
            trail_score = round(min(overlap_pct * 0.6 + release_smoothness * 0.4, 100), 1)
        else:
            overlap_pct = 0.0
            release_smoothness = 0.0
            trail_score = 0.0
        result["trail_braking"] = {
            "overlap_pct": round(overlap_pct, 1),
            "release_smoothness": round(release_smoothness, 1),
            "score": trail_score,
        }

    # --- Throttle analysis ---
    if "throttle_pct" in cd.columns:
        throttle = cd["throttle_pct"].values
        after_apex = throttle[min_speed_idx:]
        dist_after = dist[min_speed_idx:]
        time_after = time_ms[min_speed_idx:]
        # Throttle-on distance
        throttle_on_dist = None
        if len(after_apex) > 0:
            on_mask = after_apex > 10
            if np.any(on_mask):
                first_on = int(np.argmax(on_mask))
                throttle_on_dist = float(dist_after[first_on]) - float(dist[min_speed_idx])
        # Application rate: average throttle increase per second in first 0.5s of application
        app_rate = None
        if throttle_on_dist is not None and len(after_apex) > 3:
            on_idx = int(np.argmax(after_apex > 10))
            if on_idx < len(after_apex) - 1:
                dt_app = (time_after[min(on_idx + 5, len(time_after) - 1)] - time_after[on_idx]) / 1000.0
                if dt_app > 0:
                    throttle_gain = float(after_apex[min(on_idx + 5, len(after_apex) - 1)] - after_apex[on_idx])
                    app_rate = round(throttle_gain / dt_app, 1)
        # Hesitation: time spent between 10-80% throttle after apex
        partial_mask = (after_apex > 10) & (after_apex < 80)
        if len(time_after) > 1:
            dt_total = (time_after[-1] - time_after[0]) / 1000.0
            partial_time = float(np.sum(partial_mask)) / len(partial_mask) * dt_total if dt_total > 0 else 0
        else:
            partial_time = 0.0
        result["throttle"] = {
            "throttle_on_distance_after_apex_m": round(throttle_on_dist, 1) if throttle_on_dist is not None else None,
            "application_rate_pct_per_s": app_rate,
            "partial_throttle_time_s": round(partial_time, 3),
            "max_throttle_in_corner_pct": round(float(np.max(throttle)), 1),
        }

    # --- Understeer / oversteer detection ---
    has_yaw = "yaw_rate_body" in cd.columns or "yaw_rate" in cd.columns
    if has_steer and has_yaw:
        steer_vals = cd["steering_angle"].values
        yaw_col = "yaw_rate_body" if "yaw_rate_body" in cd.columns else "yaw_rate"
        yaw_vals = cd[yaw_col].values
        if len(steer_vals) > 5:
            dt = np.diff(time_ms) / 1000.0
            dt[dt == 0] = 0.001
            steer_rate = np.abs(np.diff(steer_vals) / dt)
            yaw_rate_change = np.abs(np.diff(yaw_vals) / dt)
            # Understeer: steering rate increasing but yaw not responding proportionally
            entry_zone = slice(0, min_speed_idx)
            steer_r_entry = steer_rate[entry_zone]
            yaw_r_entry = yaw_rate_change[entry_zone]
            if len(steer_r_entry) > 2 and np.mean(steer_r_entry) > 0.5:
                ratio = float(np.mean(yaw_r_entry) / np.mean(steer_r_entry)) if np.mean(steer_r_entry) > 0 else 1.0
                understeer_flag = ratio < 0.5
                oversteer_flag = ratio > 2.0
            else:
                ratio = 1.0
                understeer_flag = False
                oversteer_flag = False
            # Steering corrections after apex (sign changes = corrections)
            post_apex_steer = steer_vals[min_speed_idx:]
            if len(post_apex_steer) > 3:
                sign_changes = int(np.sum(np.diff(np.sign(np.diff(post_apex_steer))) != 0))
            else:
                sign_changes = 0
            result["steering_balance"] = {
                "yaw_to_steer_ratio": round(ratio, 2),
                "understeer_detected": understeer_flag,
                "oversteer_detected": oversteer_flag,
                "post_apex_corrections": sign_changes,
            }

    # --- Wheel slip analysis ---
    has_wheels = all(
        c in cd.columns for c in
        ["wheel_speed_fl_kph", "wheel_speed_fr_kph", "wheel_speed_rl_kph", "wheel_speed_rr_kph"]
    )
    if has_wheels and "speed_kph" in cd.columns:
        fl = cd["wheel_speed_fl_kph"].values
        fr = cd["wheel_speed_fr_kph"].values
        rl = cd["wheel_speed_rl_kph"].values
        rr = cd["wheel_speed_rr_kph"].values
        gps_spd = cd["speed_kph"].values
        front_avg = (fl + fr) / 2
        rear_avg = (rl + rr) / 2
        # Braking lockup: any wheel drops significantly below GPS speed
        min_wheel = np.minimum(np.minimum(fl, fr), np.minimum(rl, rr))
        lockup_threshold = 0.85
        lockup_samples = np.sum(min_wheel < gps_spd * lockup_threshold)
        lockup_detected = int(lockup_samples) > 2
        # Wheelspin: driven wheels (rear for RWD/AWD) faster than GPS speed
        spin_threshold = 1.05
        spin_samples = np.sum(rear_avg > gps_spd * spin_threshold)
        wheelspin_detected = int(spin_samples) > 2
        # Front-rear speed delta (slip ratio proxy)
        fr_rear_delta = float(np.mean(np.abs(front_avg - rear_avg)))
        result["wheel_slip"] = {
            "lockup_detected": lockup_detected,
            "lockup_sample_count": int(lockup_samples),
            "wheelspin_detected": wheelspin_detected,
            "wheelspin_sample_count": int(spin_samples),
            "avg_front_rear_speed_delta_kph": round(fr_rear_delta, 2),
        }

    return result


def compute_advanced_lap_metrics(
    df: pd.DataFrame, lap: dict, corners: list[DetectedCorner]
) -> dict:
    """Compute advanced metrics for all corners in a lap. Returns a summary dict."""
    lap_df = segment_lap_distance(df, lap["start_time_ms"], lap["end_time_ms"])
    if len(lap_df) == 0:
        return {"lap_number": lap["lap_number"], "corners": []}

    corner_metrics = []
    for corner in corners:
        m = compute_advanced_corner_metrics(lap_df, corner)
        if m:
            corner_metrics.append(m)

    # Overall lap friction circle
    overall_fc = None
    if "lateral_g" in lap_df.columns and "longitudinal_g" in lap_df.columns:
        lat_g = lap_df["lateral_g"].values
        lon_g = lap_df["longitudinal_g"].values
        g_mag = np.sqrt(lat_g**2 + lon_g**2)
        max_g = float(np.max(g_mag))
        if max_g > 0.05:
            overall_fc = {
                "max_g_magnitude": round(max_g, 3),
                "avg_g_utilization_pct": round(float(np.mean(g_mag) / max_g * 100), 1),
            }

    return {
        "lap_number": lap["lap_number"],
        "overall_friction_circle": overall_fc,
        "corners": corner_metrics,
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
