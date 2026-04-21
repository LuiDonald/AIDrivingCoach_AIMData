"""Known track layouts with official corner names used by the motorsport community.

When a session's venue matches a known track, we use the official corner names
instead of generic T1, T2, etc. Corner positions are approximate distances from
start/finish in meters, used to map auto-detected corners to their real names.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass

from app.services.track_segmentation import DetectedCorner


@dataclass
class KnownCorner:
    number: str
    name: str
    direction: str
    approx_distance_m: float
    description: str = ""


TRACK_DATABASE: dict[str, dict] = {
    "njmp_thunderbolt": {
        "full_name": "NJMP Thunderbolt",
        "aliases": [
            "njmp", "thunderbolt", "njmp-thunder", "njmp thunderbolt",
            "new jersey motorsports park", "thunderbolt raceway",
            "njmp - thunderbolt", "njmp_thunderbolt",
        ],
        "lat": 39.360,
        "lon": -75.070,
        "length_mi": 2.25,
        "length_m": 3621,
        "corners": [
            KnownCorner("1", "Turn 1", "right", 300, "Fast right"),
            KnownCorner("2", "Turn 2", "right", 600, "Faster right, can be flat in low-HP cars"),
            KnownCorner("3a", "Turn 3a (Chicane)", "right", 900, "Chicane entry, fairly slow right"),
            KnownCorner("3b", "Turn 3b (Chicane)", "left", 950, "Chicane mid, late apex left"),
            KnownCorner("3c", "Turn 3c (Chicane)", "right", 1000, "Chicane exit, accelerate through"),
            KnownCorner("4", "Turn 4", "right", 1250, "Fairly fast right, easy to overslow"),
            KnownCorner("5", "Turn 5", "left", 1450, "Slow left, 2nd slowest on track"),
            KnownCorner("6", "Turn 6", "right", 1750, "Fast right, lift or flat depending on HP"),
            KnownCorner("7", "Turn 7", "right", 2000, "Slower right, light braking"),
            KnownCorner("8", "Turn 8", "right", 2250, "Long right sweeper into braking for T9"),
            KnownCorner("9", "Turn 9 (Octopus)", "right", 2550, "Slowest corner on track"),
            KnownCorner("10", "Turn 10 (Octopus)", "left", 2750, "Most difficult corner, late apex key"),
            KnownCorner("11a", "Turn 11a (Snake)", "right", 2950, "First half of snake, stay flat"),
            KnownCorner("11b", "Turn 11b (Snake)", "left", 3050, "Second half of snake, stay flat"),
            KnownCorner("12", "Turn 12", "right", 3350, "Fast right, flat in low/mid HP cars"),
        ],
    },
    "watkins_glen": {
        "full_name": "Watkins Glen International",
        "aliases": [
            "watkins glen", "the glen", "wgi",
        ],
        "lat": 42.337,
        "lon": -76.927,
        "length_mi": 3.37,
        "length_m": 5430,
        "corners": [
            KnownCorner("1", "Turn 1", "right", 400),
            KnownCorner("2", "The Esses (Entry)", "left", 750),
            KnownCorner("3", "The Esses (Exit)", "right", 900),
            KnownCorner("4", "The Back Straight Chicane", "left", 1200),
            KnownCorner("5", "The Bus Stop (Entry)", "right", 2800),
            KnownCorner("6", "The Bus Stop (Exit)", "left", 2950),
            KnownCorner("7", "The Carousel", "right", 3400),
            KnownCorner("8", "The Inner Loop (Entry)", "right", 3800),
            KnownCorner("9", "The Inner Loop (Exit)", "left", 3950),
            KnownCorner("10", "The Toe of the Boot", "left", 4400),
            KnownCorner("11", "The Heel of the Boot", "right", 4700),
        ],
    },
    "vir_full": {
        "full_name": "Virginia International Raceway (Full Course)",
        "aliases": [
            "vir", "virginia international raceway", "vir full",
        ],
        "lat": 36.634,
        "lon": -79.206,
        "length_mi": 3.27,
        "length_m": 5263,
        "corners": [
            KnownCorner("1", "Turn 1 (Front Straight Right)", "right", 350),
            KnownCorner("2", "Turn 2 (Climbing Esses Entry)", "left", 600),
            KnownCorner("3", "Turn 3 (Climbing Esses Mid)", "right", 800),
            KnownCorner("4", "Turn 4 (Climbing Esses Exit)", "left", 1000),
            KnownCorner("5", "Turn 5 (Bitch)", "right", 1400),
            KnownCorner("6", "Turn 6 (Left Hook)", "left", 1700),
            KnownCorner("7", "Turn 7 (NASCAR Bend)", "right", 2100),
            KnownCorner("8", "Turn 8 (Hog Pen)", "right", 2500),
            KnownCorner("9", "Turn 9 (Oak Tree)", "right", 3200),
            KnownCorner("10", "Turn 10 (South Bend Entry)", "right", 3600),
            KnownCorner("11", "Turn 11 (South Bend Exit)", "left", 3800),
            KnownCorner("12", "Turn 12 (Roller Coaster)", "right", 4200),
            KnownCorner("13", "Turn 13 (Snake Entry)", "left", 4600),
            KnownCorner("14", "Turn 14 (Snake Exit)", "right", 4800),
        ],
    },
    "road_america": {
        "full_name": "Road America",
        "aliases": [
            "road america", "elkhart lake",
        ],
        "lat": 43.800,
        "lon": -87.989,
        "length_mi": 4.048,
        "length_m": 6515,
        "corners": [
            KnownCorner("1", "Turn 1", "left", 400),
            KnownCorner("2", "Turn 2", "right", 600),
            KnownCorner("3", "Turn 3", "right", 900),
            KnownCorner("4", "Turn 4", "right", 1200),
            KnownCorner("5", "Turn 5 (Moraine Sweep)", "left", 1800),
            KnownCorner("6", "Turn 6 (The Kink)", "left", 3200),
            KnownCorner("7", "Turn 7 (Hurry Downs)", "right", 3800),
            KnownCorner("8", "Turn 8 (Canada Corner)", "right", 4600),
            KnownCorner("9", "Turn 9", "left", 5000),
            KnownCorner("10", "Turn 10", "right", 5300),
            KnownCorner("11", "Turn 11 (Kettle Bottoms Entry)", "left", 5600),
            KnownCorner("12", "Turn 12 (Kettle Bottoms Exit)", "right", 5900),
            KnownCorner("13", "Turn 13 (Carousel)", "right", 6100),
            KnownCorner("14", "Turn 14 (Thunder Valley)", "right", 6300),
        ],
    },
}


def match_track(
    venue_name: str | None,
    track_name: str | None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
) -> dict | None:
    """Try to match a session's venue/track to a known track layout.

    Matches by name first, then falls back to GPS proximity (~2 km radius).
    """
    search_terms = []
    if venue_name:
        search_terms.append(venue_name.lower().strip())
    if track_name:
        search_terms.append(track_name.lower().strip())

    if search_terms:
        for track_key, track_data in TRACK_DATABASE.items():
            for alias in track_data["aliases"]:
                for term in search_terms:
                    if alias in term or term in alias:
                        return track_data

    if gps_lat is not None and gps_lon is not None:
        import math
        best_match = None
        best_dist = float("inf")
        for track_key, track_data in TRACK_DATABASE.items():
            t_lat = track_data.get("lat")
            t_lon = track_data.get("lon")
            if t_lat is None or t_lon is None:
                continue
            dlat = math.radians(gps_lat - t_lat)
            dlon = math.radians(gps_lon - t_lon)
            a = (math.sin(dlat / 2) ** 2 +
                 math.cos(math.radians(gps_lat)) * math.cos(math.radians(t_lat)) *
                 math.sin(dlon / 2) ** 2)
            dist_m = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist_m < best_dist:
                best_dist = dist_m
                best_match = track_data
        if best_match and best_dist < 2000:
            return best_match

    return None


def corners_from_known_track(
    known_track: dict,
    lap_df: pd.DataFrame,
) -> list[DetectedCorner]:
    """Create DetectedCorner objects from a known track's corner database.

    Uses the known corner positions (scaled to match actual lap distance) and
    lateral-g telemetry to find real apex locations near each expected position.
    Falls back to auto-detection if the telemetry is missing required columns.
    """
    known_corners: list[KnownCorner] = known_track["corners"]
    known_length = known_track.get("length_m", 0)

    if not known_corners or "distance_m" not in lap_df.columns:
        return []
    if "lateral_g" not in lap_df.columns:
        return []

    distance = lap_df["distance_m"].values
    lat_g = lap_df["lateral_g"].values.copy()
    lat_g = np.nan_to_num(lat_g, nan=0.0)
    abs_g = np.abs(lat_g)
    actual_length = float(distance[-1])

    scale = actual_length / known_length if known_length > 0 else 1.0
    scaled_positions = [kc.approx_distance_m * scale for kc in known_corners]

    # Build search boundaries: midpoint between adjacent known corners
    boundaries: list[tuple[float, float]] = []
    for i in range(len(scaled_positions)):
        if i == 0:
            start = max(0.0, scaled_positions[i] - 150)
        else:
            start = (scaled_positions[i - 1] + scaled_positions[i]) / 2

        if i == len(scaled_positions) - 1:
            end = min(actual_length, scaled_positions[i] + 150)
        else:
            end = (scaled_positions[i] + scaled_positions[i + 1]) / 2

        boundaries.append((start, end))

    g_threshold = 0.2
    detected: list[DetectedCorner] = []

    for i, kc in enumerate(known_corners):
        bound_start, bound_end = boundaries[i]

        start_idx = int(np.searchsorted(distance, bound_start))
        end_idx = int(np.searchsorted(distance, bound_end))
        start_idx = max(0, min(start_idx, len(distance) - 1))
        end_idx = max(start_idx + 1, min(end_idx, len(distance) - 1))

        if end_idx - start_idx < 3:
            continue

        window_g = abs_g[start_idx:end_idx + 1]
        apex_local = int(np.argmax(window_g))
        apex_idx = start_idx + apex_local

        # Expand from apex until g drops below threshold
        corner_start = apex_idx
        while corner_start > start_idx and abs_g[corner_start] > g_threshold:
            corner_start -= 1
        corner_end = apex_idx
        while corner_end < end_idx and abs_g[corner_end] > g_threshold:
            corner_end += 1

        corner_start = max(start_idx, corner_start)
        corner_end = min(end_idx, corner_end)

        detected.append(DetectedCorner(
            corner_id=i + 1,
            corner_type=kc.direction,
            start_distance_m=float(distance[corner_start]),
            end_distance_m=float(distance[corner_end]),
            apex_distance_m=float(distance[apex_idx]),
            apex_lateral_g=float(abs_g[apex_idx]),
            start_idx=int(corner_start),
            end_idx=int(corner_end),
            apex_idx=int(apex_idx),
        ))

    return detected


def build_known_name_map(known_track: dict) -> dict[int, str]:
    """Direct mapping from sequential corner_id (1-based) to the known corner
    name. Use this instead of ``map_detected_to_known`` when the corners were
    created by ``corners_from_known_track`` (the ID-to-name correspondence is
    guaranteed by construction).
    """
    return {i + 1: kc.name for i, kc in enumerate(known_track["corners"])}


def build_known_label_map(known_track: dict) -> dict[int, str]:
    """Direct mapping from sequential corner_id (1-based) to the known corner
    short label (e.g. "3a", "12").
    """
    return {i + 1: kc.number for i, kc in enumerate(known_track["corners"])}


def map_detected_to_known(
    detected_corners: list[dict],
    known_track: dict,
    track_length_m: float | None = None,
) -> list[dict]:
    """Map auto-detected corners to known corner names by proximity.

    Each detected corner gets matched to the nearest known corner based on
    apex distance. Known corners that don't have a detected match get their
    own entry.
    """
    known = known_track["corners"]
    result = []

    used_known = set()
    for det in detected_corners:
        apex_d = det.get("apex_distance_m", 0)
        best_match = None
        best_dist = float("inf")

        for i, kc in enumerate(known):
            if i in used_known:
                continue
            dist = abs(kc.approx_distance_m - apex_d)
            if dist < best_dist:
                best_dist = dist
                best_match = i

        threshold = (track_length_m or known_track.get("length_m", 5000)) * 0.05
        if best_match is not None and best_dist < threshold:
            kc = known[best_match]
            used_known.add(best_match)
            result.append({
                **det,
                "label": kc.number,
                "name": kc.name,
                "description": kc.description,
            })
        else:
            result.append({
                **det,
                "label": str(det.get("corner_id", "?")),
                "name": f"Turn {det.get('corner_id', '?')}",
                "description": "",
            })

    return result
