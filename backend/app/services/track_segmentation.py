"""Auto-detect track corners from GPS path curvature and lateral g-force data."""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from dataclasses import dataclass


@dataclass
class DetectedCorner:
    corner_id: int
    corner_type: str  # "left" or "right"
    start_distance_m: float
    end_distance_m: float
    apex_distance_m: float
    apex_lateral_g: float
    start_idx: int
    end_idx: int
    apex_idx: int


def compute_curvature(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Compute path curvature from GPS coordinates.

    Uses the change in heading angle over distance to determine curvature.
    Positive = right turn, negative = left turn.
    """
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)

    x = 6371000 * lon_r * np.cos(np.mean(lat_r))
    y = 6371000 * lat_r

    if len(x) < 7:
        return np.zeros_like(x)

    window = min(11, len(x) - 1)
    if window % 2 == 0:
        window -= 1
    if window < 5:
        return np.zeros_like(x)

    x_smooth = savgol_filter(x, window, 3)
    y_smooth = savgol_filter(y, window, 3)

    dx = np.gradient(x_smooth)
    dy = np.gradient(y_smooth)
    ddx = np.gradient(dx)
    ddy = np.gradient(dy)

    denom = (dx**2 + dy**2) ** 1.5
    denom[denom < 1e-10] = 1e-10
    curvature = (dx * ddy - dy * ddx) / denom

    return curvature


def detect_corners(
    df: pd.DataFrame,
    min_lateral_g: float = 0.3,
    min_corner_duration_m: float = 20.0,
    merge_gap_m: float = 30.0,
) -> list[DetectedCorner]:
    """Detect corners from telemetry data.

    Uses lateral g-force as the primary signal with GPS curvature for direction.
    """
    if "lateral_g" not in df.columns or "distance_m" not in df.columns:
        return []

    lat_g = df["lateral_g"].values.copy()
    distance = df["distance_m"].values

    if len(lat_g) < 20:
        return []

    lat_g = np.nan_to_num(lat_g, nan=0.0)

    abs_g = np.abs(lat_g)

    in_corner = abs_g >= min_lateral_g

    corners_raw = []
    i = 0
    while i < len(in_corner):
        if in_corner[i]:
            start_idx = i
            while i < len(in_corner) and in_corner[i]:
                i += 1
            end_idx = i - 1

            corner_dist = distance[end_idx] - distance[start_idx]
            if corner_dist >= min_corner_duration_m:
                apex_idx = start_idx + np.argmax(abs_g[start_idx : end_idx + 1])

                avg_lat_g = np.mean(lat_g[start_idx : end_idx + 1])
                direction = "right" if avg_lat_g > 0 else "left"

                corners_raw.append({
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "apex_idx": apex_idx,
                    "direction": direction,
                    "apex_g": abs_g[apex_idx],
                })
        else:
            i += 1

    corners_merged = []
    for c in corners_raw:
        if corners_merged and c["direction"] == corners_merged[-1]["direction"]:
            gap = distance[c["start_idx"]] - distance[corners_merged[-1]["end_idx"]]
            if gap < merge_gap_m:
                prev = corners_merged[-1]
                prev["end_idx"] = c["end_idx"]
                if c["apex_g"] > prev["apex_g"]:
                    prev["apex_idx"] = c["apex_idx"]
                    prev["apex_g"] = c["apex_g"]
                continue
        corners_merged.append(c)

    # Extend corner boundaries slightly to capture entry/exit phases
    extend_m = 15.0
    detected = []
    for i, c in enumerate(corners_merged):
        start_d = distance[c["start_idx"]]
        end_d = distance[c["end_idx"]]

        ext_start = max(0, np.searchsorted(distance, start_d - extend_m))
        ext_end = min(len(distance) - 1, np.searchsorted(distance, end_d + extend_m))

        detected.append(DetectedCorner(
            corner_id=i + 1,
            corner_type=c["direction"],
            start_distance_m=float(distance[ext_start]),
            end_distance_m=float(distance[ext_end]),
            apex_distance_m=float(distance[c["apex_idx"]]),
            apex_lateral_g=float(c["apex_g"]),
            start_idx=int(ext_start),
            end_idx=int(ext_end),
            apex_idx=int(c["apex_idx"]),
        ))

    return detected


def segment_lap_distance(df: pd.DataFrame, lap_start_ms: int, lap_end_ms: int) -> pd.DataFrame:
    """Extract a single lap's data and reset distance to 0 at lap start."""
    lap_df = df[(df["time_ms"] >= lap_start_ms) & (df["time_ms"] < lap_end_ms)].copy()
    if len(lap_df) > 0 and "distance_m" in lap_df.columns:
        lap_df["distance_m"] = lap_df["distance_m"] - lap_df["distance_m"].iloc[0]
    return lap_df
