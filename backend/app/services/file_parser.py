"""Parse AIM SOLO / SOLO DL telemetry files (.xrk, .xrz, .csv) into DataFrames."""

import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field


KNOWN_CHANNEL_ALIASES = {
    # Speed -- units vary by source:
    #   XRK/XRZ: GPS Speed is m/s, SpeedAverage/WheelSpd are kph
    #   AIM CSV: GPS_Speed is mph
    "GPS Speed": "gps_speed_ms",
    "GPS_Speed": "speed_mph",
    "SpeedAverage": "speed_avg_kph",
    # GPS position
    "GPS Latitude": "gps_lat",
    "GPS_Latitude": "gps_lat",
    "Latitude": "gps_lat",
    "GPS Longitude": "gps_lon",
    "GPS_Longitude": "gps_lon",
    "Longitude": "gps_lon",
    "GPS Altitude": "gps_alt",
    "GPS_Altitude": "gps_alt",
    "GPS_Elevation": "gps_elevation",
    # Heading and gyro
    "GPS Heading": "heading",
    "GPS_Heading": "heading",
    "GPS Gyro": "yaw_rate",
    "GPS_Gyro": "yaw_rate",
    "GPS_Slope": "gps_slope",
    "GPS_Nsat": "gps_satellites",
    "GPS_PosAccuracy": "gps_pos_accuracy",
    "GPS_SpdAccuracy": "gps_spd_accuracy",
    # Acceleration -- AIM CSV uses LateralAcc/InlineAcc (body), GPS_LatAcc/GPS_LonAcc (GPS-derived)
    "GPS_LatAcc": "lateral_g",
    "GPS_LonAcc": "longitudinal_g",
    "GPS_LateralAcc": "lateral_g",
    "GPS_InlineAcc": "longitudinal_g",
    "LateralAcc": "lateral_g_body",
    "InlineAcc": "longitudinal_g_body",
    "VerticalAcc": "vertical_g",
    "Lateral Acc": "lateral_g",
    "Longitudinal Acc": "longitudinal_g",
    "Lat Acc": "lateral_g",
    "Lon Acc": "longitudinal_g",
    # Rotation rates
    "RollRate": "roll_rate",
    "PitchRate": "pitch_rate",
    "YawRate": "yaw_rate_body",
    # Engine
    "Engine RPM": "rpm",
    "RPM": "rpm",
    "Gear": "gear",
    "MAPCorrected": "map_corrected",
    "MAP": "map_psi",
    "Baro": "baro_psi",
    "Lambda": "lambda",
    # Throttle / pedal
    "Throttle": "throttle_pct",
    "TPS": "throttle_pct",
    "PPS": "pedal_pct",
    "Throttle Position": "throttle_pct",
    # Brakes
    "Brake Pressure": "brake_pressure",
    "BrakePress": "brake_pressure",
    "Brake": "brake_pressure",
    "BrakeSw": "brake_switch",
    "ClutchSw": "clutch_switch",
    # Steering
    "Steering Angle": "steering_angle",
    "SteerAngle": "steering_angle",
    # Wheel speeds (kph in XRK, mph in AIM CSV — CSV path handles conversion)
    "WheelSpdFL": "wheel_speed_fl_kph",
    "WheelSpdFR": "wheel_speed_fr_kph",
    "WheelSpdRL": "wheel_speed_rl_kph",
    "WheelSpdRR": "wheel_speed_rr_kph",
    # Temperatures
    "Water Temp": "water_temp",
    "ECT": "water_temp",
    "Oil Temp": "oil_temp",
    "OilTemp": "oil_temp",
    "Oil Pressure": "oil_pressure",
    "Air Temp": "air_temp",
    "IntakeAirT": "intake_air_temp",
    "AmbientTemp": "ambient_temp",
    "CAT1": "cat1_temp",
    "CAT2": "cat2_temp",
    # Electrical
    "Battery": "battery_v",
    "Internal Battery": "internal_battery_v",
    "External Voltage": "external_voltage_v",
    # Magnetometer
    "MagnetomX": "magnetom_x",
    "MagnetomY": "magnetom_y",
    "MagnetomZ": "magnetom_z",
}

# AIM CSV metadata keys in the header section
AIM_CSV_META_KEYS = {
    "Format", "Venue", "Vehicle", "User", "Data Source",
    "Comment", "Date", "Time", "Sample Rate", "Duration", "Segment",
}


@dataclass
class ParsedSession:
    df: pd.DataFrame
    laps: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    channels: list[str] = field(default_factory=list)
    raw_channels: list[str] = field(default_factory=list)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map known AIM channel names to standardized column names."""
    rename_map = {}
    for col in df.columns:
        stripped = col.strip().strip('"')
        if stripped in KNOWN_CHANNEL_ALIASES:
            rename_map[col] = KNOWN_CHANNEL_ALIASES[stripped]

    df = df.rename(columns=rename_map)

    if "timecodes" in df.columns:
        df = df.rename(columns={"timecodes": "time_ms"})

    return df


def _convert_mph_to_kph(df: pd.DataFrame) -> pd.DataFrame:
    """Convert AIM CSV speed columns from mph to kph for consistency."""
    mph_to_kph = 1.60934
    if "speed_mph" in df.columns:
        df["speed_kph"] = df["speed_mph"] * mph_to_kph
    elif "speed_avg_kph" in df.columns and "speed_kph" not in df.columns:
        df["speed_kph"] = df["speed_avg_kph"]
    return df


def _compute_distance(df: pd.DataFrame) -> pd.DataFrame:
    """Compute cumulative distance from GPS coordinates if not present."""
    if "distance_m" in df.columns:
        return df

    if "gps_lat" in df.columns and "gps_lon" in df.columns:
        lat = np.radians(df["gps_lat"].values)
        lon = np.radians(df["gps_lon"].values)
        dlat = np.diff(lat, prepend=lat[0])
        dlon = np.diff(lon, prepend=lon[0])
        a = np.sin(dlat / 2) ** 2 + np.cos(lat) * np.cos(np.roll(lat, 1)) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        segment_dist = 6371000 * c
        segment_dist[0] = 0
        df["distance_m"] = np.cumsum(segment_dist)
    elif "speed_kph" in df.columns and "time_ms" in df.columns:
        speed_ms = df["speed_kph"].values / 3.6
        dt = np.diff(df["time_ms"].values, prepend=df["time_ms"].values[0]) / 1000.0
        df["distance_m"] = np.cumsum(speed_ms * dt)

    return df


def _ensure_g_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure lateral_g and longitudinal_g columns exist.

    Falls back to body-fixed accelerometer channels if GPS-derived
    accelerations are not available.
    """
    if "lateral_g" not in df.columns and "lateral_g_body" in df.columns:
        df["lateral_g"] = df["lateral_g_body"]
    if "longitudinal_g" not in df.columns and "longitudinal_g_body" in df.columns:
        df["longitudinal_g"] = df["longitudinal_g_body"]
    return df


def _convert_xrk_speeds(df: pd.DataFrame) -> pd.DataFrame:
    """Convert XRK/XRZ speed channels to a unified speed_kph column.

    AIM SOLO GPS Speed is in m/s; SpeedAverage and WheelSpd are in kph.
    Prefer GPS Speed (highest accuracy), fall back to SpeedAverage.
    """
    if "gps_speed_ms" in df.columns:
        df["speed_kph"] = df["gps_speed_ms"] * 3.6

    elif "speed_avg_kph" in df.columns:
        df["speed_kph"] = df["speed_avg_kph"]

    return df


def parse_xrk(file_path: str) -> ParsedSession:
    """Parse an AIM .xrk or .xrz file using libxrk."""
    try:
        from libxrk import aim_xrk
    except ImportError:
        raise ImportError(
            "libxrk is required for .xrk/.xrz files. Install with: pip install libxrk"
        )

    log = aim_xrk(file_path)

    raw_channels = list(log.channels.keys())

    merged = log.get_channels_as_table()
    df = merged.to_pandas()
    df = _normalize_columns(df)
    df = _convert_xrk_speeds(df)
    df = _ensure_g_columns(df)

    laps = []
    if log.laps and log.laps.num_rows > 0:
        for i in range(log.laps.num_rows):
            lap_num = log.laps.column("num")[i].as_py()
            start = log.laps.column("start_time")[i].as_py()
            end = log.laps.column("end_time")[i].as_py()
            lap_time_s = (end - start) / 1000.0
            if lap_time_s > 5:
                laps.append({
                    "lap_number": lap_num,
                    "start_time_ms": start,
                    "end_time_ms": end,
                    "lap_time_s": round(lap_time_s, 3),
                })

    meta = {}
    if hasattr(log, "metadata") and log.metadata:
        meta = dict(log.metadata) if not isinstance(log.metadata, dict) else log.metadata

    df = _compute_distance(df)

    normalized_channels = [c for c in df.columns if c != "time_ms"]

    return ParsedSession(
        df=df,
        laps=laps,
        metadata=meta,
        channels=normalized_channels,
        raw_channels=raw_channels,
    )


def _read_aim_csv_header(file_path: str) -> tuple[dict, int]:
    """Read the AIM CSV metadata header and find where data starts.

    AIM Race Studio CSV format:
      Lines 1-N: Metadata as "Key","Value" pairs (Value may span multiple lines)
      Blank line
      Column names row (quoted, trailing comma)
      Column names row (duplicate)
      Units row (contains degree symbols in Latin-1)
      Channel numbers row
      Blank line
      Data rows (numeric CSV)

    Returns (metadata_dict, data_start_line_number).
    """
    metadata = {}
    data_start = 0
    column_header_line = -1

    # AIM uses Latin-1 encoding for degree symbols (0xB0)
    with open(file_path, "r", encoding="latin-1") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip().strip("\r")

        # Skip blank lines
        if not line:
            i += 1
            continue

        # Detect the column header row: starts with "Time" and has many commas
        # (distinguishes from the metadata "Time","13:22:35" which has only 1 comma)
        if (line.startswith('"Time"') or line.startswith('"time"')) and line.count(",") > 5:
            column_header_line = i
            # Skip: header row, duplicate header, units row, channel numbers
            data_start = i + 4
            # Advance past blank lines to first data row
            while data_start < len(lines) and not lines[data_start].strip().strip("\r"):
                data_start += 1
            break

        # Parse "Key","Value" metadata lines
        if line.startswith('"'):
            parts = line.split('","', 1)
            if len(parts) == 2:
                key = parts[0].strip('"')
                raw_val = parts[1].rstrip()

                # Handle multi-line quoted values (e.g. Comment field)
                # The value is complete when we find a line ending with "
                while not raw_val.endswith('"') and i + 1 < len(lines):
                    i += 1
                    next_line = lines[i].strip().strip("\r")
                    raw_val += "\n" + next_line

                val = raw_val.strip('"')
                if key in AIM_CSV_META_KEYS:
                    metadata[key] = val

        i += 1

    return metadata, data_start, column_header_line


def parse_csv(file_path: str) -> ParsedSession:
    """Parse a CSV exported from AIM RaceStudio.

    Handles the AIM-specific multi-line header format with metadata,
    duplicate column names, units row, and channel numbers.
    """
    metadata, data_start, column_header_line = _read_aim_csv_header(file_path)

    is_aim_format = bool(metadata.get("Format") or metadata.get("Venue") or metadata.get("Data Source"))

    if is_aim_format:
        aim_encoding = "latin-1"

        # Read the column header line directly from the file
        with open(file_path, "r", encoding=aim_encoding) as f:
            all_lines = f.readlines()

        header_line = all_lines[column_header_line].strip().strip("\r\n")
        # Parse quoted CSV column names, strip quotes and trailing empties
        import csv
        import io
        reader = csv.reader(io.StringIO(header_line))
        columns = [c.strip() for c in next(reader) if c.strip()]

        # Read the actual data rows (no header in this read)
        df = pd.read_csv(
            file_path, skiprows=data_start, header=None,
            encoding=aim_encoding, skipinitialspace=True,
            on_bad_lines="skip",
        )

        # Trim to the expected number of columns
        if len(df.columns) > len(columns):
            df = df.iloc[:, :len(columns)]
        df.columns = columns[:len(df.columns)]

        # Drop rows that aren't numeric data
        df = df[pd.to_numeric(df.iloc[:, 0], errors="coerce").notna()].copy()
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        raw_channels = list(columns)
    else:
        # Fallback: plain CSV without AIM header
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        raw_channels = list(df.columns)

    # Convert Time (seconds) -> time_ms
    if "Time" in df.columns and "time_ms" not in df.columns:
        time_vals = df["Time"].values
        if len(time_vals) > 0 and time_vals[-1] < 100000:
            df["time_ms"] = (time_vals * 1000).astype(int)
        else:
            df.rename(columns={"Time": "time_ms"}, inplace=True)

    # Convert Distance (km) -> distance_m if present
    if "Distance" in df.columns:
        df["distance_m"] = df["Distance"] * 1000.0

    df = _normalize_columns(df)
    df = _convert_mph_to_kph(df)

    # If no lateral_g from GPS, fall back to body-mounted accelerometer
    if "lateral_g" not in df.columns and "lateral_g_body" in df.columns:
        df["lateral_g"] = df["lateral_g_body"]
    if "longitudinal_g" not in df.columns and "longitudinal_g_body" in df.columns:
        df["longitudinal_g"] = df["longitudinal_g_body"]

    df = _compute_distance(df)

    laps = _detect_laps_from_csv(df, metadata)
    normalized_channels = [c for c in df.columns if c not in ("time_ms", "Time", "Distance")]

    return ParsedSession(
        df=df,
        laps=laps,
        metadata=metadata,
        channels=normalized_channels,
        raw_channels=raw_channels,
    )


def _detect_laps_from_csv(df: pd.DataFrame, metadata: dict) -> list[dict]:
    """Detect laps from AIM CSV data.

    AIM CSVs may be single-lap exports (Segment header tells which lap)
    or multi-lap exports. Handles both cases.
    """
    # Check for explicit lap column
    lap_col = None
    for name in ("Lap", "lap", "LapNumber"):
        if name in df.columns:
            lap_col = name
            break

    if lap_col:
        laps = []
        for lap_num in sorted(df[lap_col].unique()):
            lap_data = df[df[lap_col] == lap_num]
            if len(lap_data) < 10:
                continue
            start = int(lap_data["time_ms"].iloc[0])
            end = int(lap_data["time_ms"].iloc[-1])
            lap_time_s = (end - start) / 1000.0
            if lap_time_s > 5:
                laps.append({
                    "lap_number": int(lap_num),
                    "start_time_ms": start,
                    "end_time_ms": end,
                    "lap_time_s": round(lap_time_s, 3),
                })
        return laps

    # Single-lap export: extract lap info from Segment metadata
    segment = metadata.get("Segment", "")
    lap_number = 1
    lap_time_from_header = None

    if segment:
        # Parse "Lap 4 - 1:29.688" format
        import re
        match = re.match(r"Lap\s+(\d+)\s*-\s*(\d+):(\d+\.?\d*)", segment)
        if match:
            lap_number = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            lap_time_from_header = minutes * 60 + seconds

    if "time_ms" in df.columns and len(df) > 10:
        start = int(df["time_ms"].iloc[0])
        end = int(df["time_ms"].iloc[-1])
        lap_time_s = lap_time_from_header or (end - start) / 1000.0
        return [{
            "lap_number": lap_number,
            "start_time_ms": start,
            "end_time_ms": end,
            "lap_time_s": round(lap_time_s, 3),
        }]

    return []


def parse_file(file_path: str) -> ParsedSession:
    """Auto-detect file format and parse."""
    ext = Path(file_path).suffix.lower()
    if ext in (".xrk", ".xrz"):
        return parse_xrk(file_path)
    elif ext == ".csv":
        return parse_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .xrk, .xrz, .csv")
