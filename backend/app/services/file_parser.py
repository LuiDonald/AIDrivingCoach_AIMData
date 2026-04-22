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
    "GPS_Yaw_Rate": "yaw_rate",
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
    "Throttle_Pos": "throttle_pct",
    "OBDII_TPS": "obdii_tps",
    # Brakes
    "Brake Pressure": "brake_pressure",
    "BrakePress": "brake_pressure",
    "Brake": "brake_pressure",
    "Brake_Pressure": "brake_pressure",
    "BrakeSw": "brake_switch",
    "BrakeSW": "brake_switch",
    "ClutchSw": "clutch_switch",
    # Steering
    "Steering Angle": "steering_angle",
    "SteerAngle": "steering_angle",
    "Steering_Angle": "steering_angle",
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
    seen_targets: set[str] = set()
    for col in df.columns:
        stripped = col.strip().strip('"')
        if stripped in KNOWN_CHANNEL_ALIASES:
            target = KNOWN_CHANNEL_ALIASES[stripped]
            if target not in seen_targets:
                rename_map[col] = target
                seen_targets.add(target)

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


PTP_COLUMNS = {
    "brakePressure", "velocity", "lateralAcceleration",
    "longitudinalAcceleration", "pedalForce", "engineSpeed",
    "steeringAngle", "timestamp", "laptime",
}

PTP_COLUMN_MAP = {
    "velocity": "speed_kph",
    "engineSpeed": "rpm",
    "currentGear": "gear",
    "steeringAngle": "steering_angle",
    "brakePressure": "brake_pressure",
    "pedalForce": "throttle_pct",
    "latitude": "gps_lat",
    "longitude": "gps_lon",
    "distance": "distance_m",
    "gierrate": "yaw_rate",
    "oversteering": "oversteer_flag",
    "understeering": "understeer_flag",
    "tireSpeedFrontLeft": "wheel_speed_fl_kph",
    "tireSpeedFrontRight": "wheel_speed_fr_kph",
    "tireSpeedRearLeft": "wheel_speed_rl_kph",
    "tireSpeedRearRight": "wheel_speed_rr_kph",
    "tirePressureFrontLeft": "tire_pressure_fl",
    "tirePressureFrontRight": "tire_pressure_fr",
    "tirePressureRearLeft": "tire_pressure_rl",
    "tirePressureRearRight": "tire_pressure_rr",
}

PTP_STRING_COLUMNS = {
    "electronicStabilityProgram", "gearSelection",
    "wpoCharismaDamper", "wpoCharismaMotor", "wpoCharismaTransmission",
}


def _is_ptp_csv(file_path: str) -> bool:
    """Detect Porsche Track Precision CSV by checking header columns."""
    with open(file_path, "r", encoding="utf-8") as f:
        header = f.readline().strip()
    cols = {c.strip() for c in header.split(",")}
    return len(cols & PTP_COLUMNS) >= 5


def _detect_ptp_laps(df: pd.DataFrame) -> list[dict]:
    """Detect laps from laptime column resets in PTP data."""
    if "laptime" not in df.columns or "time_ms" not in df.columns:
        return []

    laptime = df["laptime"].values
    time_ms = df["time_ms"].values

    boundaries = [0]
    for i in range(1, len(laptime)):
        if laptime[i] < laptime[i - 1] - 0.5:
            boundaries.append(i)
    boundaries.append(len(df))

    laps = []
    for lap_num, (start_idx, end_idx) in enumerate(
        zip(boundaries[:-1], boundaries[1:]), start=1
    ):
        if end_idx - start_idx < 10:
            continue
        start_t = int(time_ms[start_idx])
        end_t = int(time_ms[end_idx - 1])
        lap_time_s = (end_t - start_t) / 1000.0
        if lap_time_s > 5:
            laps.append({
                "lap_number": lap_num,
                "start_time_ms": start_t,
                "end_time_ms": end_t,
                "lap_time_s": round(lap_time_s, 3),
            })

    return laps


def parse_ptp_csv(file_path: str) -> ParsedSession:
    """Parse a Porsche Track Precision CSV export."""
    df = pd.read_csv(file_path, encoding="utf-8", na_values=["NULL", "null", "nan"])

    raw_channels = list(df.columns)

    # Drop string-only columns before numeric conversion
    drop_cols = [c for c in PTP_STRING_COLUMNS if c in df.columns]
    mode_info = {}
    for col in ("wpoCharismaMotor", "wpoCharismaDamper", "wpoCharismaTransmission"):
        if col in df.columns:
            mode_val = df[col].dropna().mode()
            if len(mode_val) > 0:
                mode_info[col] = str(mode_val.iloc[0])
    df = df.drop(columns=drop_cols, errors="ignore")

    # Convert gear column: "N" → 0, numeric strings stay
    if "currentGear" in df.columns:
        df["currentGear"] = pd.to_numeric(
            df["currentGear"].replace({"N": 0, "R": -1}), errors="coerce"
        )

    # Coerce remaining columns to numeric
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Timestamp → relative time_ms (offset from session start)
    if "timestamp" in df.columns:
        ts = df["timestamp"].values
        df["time_ms"] = (ts - ts[0]).astype(int)

    # Convert accelerations: m/s² → G
    if "lateralAcceleration" in df.columns:
        df["lateral_g"] = df["lateralAcceleration"] / 9.81
        df = df.drop(columns=["lateralAcceleration"])
    if "longitudinalAcceleration" in df.columns:
        df["longitudinal_g"] = df["longitudinalAcceleration"] / 9.81
        df = df.drop(columns=["longitudinalAcceleration"])

    # Scale pedalForce (0-1) → throttle_pct (0-100)
    if "pedalForce" in df.columns:
        df["pedalForce"] = df["pedalForce"] * 100.0

    # Rename mapped columns
    rename = {k: v for k, v in PTP_COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Drop leftover unmapped columns
    df = df.drop(columns=["timestamp", "laptime"], errors="ignore")

    df = _compute_distance(df)

    # Detect laps before we drop laptime (re-read for lap detection)
    raw_df = pd.read_csv(file_path, encoding="utf-8", na_values=["NULL", "null", "nan"])
    for col in raw_df.columns:
        if raw_df[col].dtype == object:
            raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce")
    if "timestamp" in raw_df.columns:
        ts = raw_df["timestamp"].values
        raw_df["time_ms"] = (ts - ts[0]).astype(int)
    laps = _detect_ptp_laps(raw_df)

    # Build metadata from filename and driving modes
    import re
    fname = Path(file_path).stem
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
    metadata = {
        "Data Source": "Porsche Track Precision",
        "Device Name": "Porsche Track Precision",
        **mode_info,
    }
    if date_match:
        metadata["Date"] = date_match.group(1)

    # Try to detect track from median GPS coordinates
    if "gps_lat" in df.columns and "gps_lon" in df.columns:
        med_lat = df["gps_lat"].dropna().median()
        med_lon = df["gps_lon"].dropna().median()
        if pd.notna(med_lat) and pd.notna(med_lon):
            metadata["gps_lat"] = float(med_lat)
            metadata["gps_lon"] = float(med_lon)

    normalized_channels = [
        c for c in df.columns if c not in ("time_ms", "laptime")
    ]

    return ParsedSession(
        df=df,
        laps=laps,
        metadata=metadata,
        channels=normalized_channels,
        raw_channels=raw_channels,
    )


def parse_file(file_path: str) -> ParsedSession:
    """Auto-detect file format and parse."""
    ext = Path(file_path).suffix.lower()
    if ext in (".xrk", ".xrz"):
        return parse_xrk(file_path)
    elif ext == ".csv":
        if _is_ptp_csv(file_path):
            return parse_ptp_csv(file_path)
        return parse_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .xrk, .xrz, .csv")


def parse_file_bytes(filename: str, content: bytes) -> ParsedSession:
    """Parse telemetry data from in-memory bytes using a temporary file."""
    import tempfile
    ext = Path(filename).suffix.lower()
    if ext not in (".xrk", ".xrz", ".csv"):
        raise ValueError(f"Unsupported file format: {ext}. Supported: .xrk, .xrz, .csv")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return parse_file(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
