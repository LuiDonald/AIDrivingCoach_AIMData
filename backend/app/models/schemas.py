from pydantic import BaseModel
from datetime import datetime
from enum import Enum


# --- Enums ---

class DrivetrainType(str, Enum):
    FWD = "FWD"
    RWD = "RWD"
    AWD = "AWD"

class TrackCondition(str, Enum):
    DRY = "dry"
    DAMP = "damp"
    WET = "wet"

class AeroLevel(str, Enum):
    NONE = "none"
    MILD = "mild"
    FULL = "full"

class WearPattern(str, Enum):
    EVEN = "even"
    INSIDE_HEAVY = "inside_heavy"
    OUTSIDE_HEAVY = "outside_heavy"
    CENTER_HEAVY = "center_heavy"
    CUPPING = "cupping"

class PhotoType(str, Enum):
    TIRE_FL = "tire_fl"
    TIRE_FR = "tire_fr"
    TIRE_RL = "tire_rl"
    TIRE_RR = "tire_rr"
    CAR_FRONT = "car_front"
    CAR_SIDE = "car_side"
    CAR_REAR = "car_rear"
    CAR_34 = "car_34"


# --- Vehicle & Setup ---

class VehicleInfo(BaseModel):
    name: str | None = None
    weight_lbs: float | None = None
    power_hp: float | None = None
    drivetrain: DrivetrainType | None = None


class AeroConfig(BaseModel):
    aero_level: AeroLevel = AeroLevel.NONE
    components: list[str] = []
    vehicle_type: str | None = None
    ride_height: str | None = None
    notable_features: list[str] = []


class TirePressures(BaseModel):
    fl: float | None = None
    fr: float | None = None
    rl: float | None = None
    rr: float | None = None


class TireAnalysis(BaseModel):
    position: str
    compound: str | None = None
    wear_pattern: WearPattern | None = None
    wear_severity_pct: float | None = None
    heat_evidence: str | None = None
    condition_summary: str | None = None
    photo_path: str | None = None


# --- Weather ---

class WeatherData(BaseModel):
    ambient_temp_f: float | None = None
    track_temp_f: float | None = None
    humidity_pct: float | None = None
    wind_speed_mph: float | None = None
    wind_direction: str | None = None
    conditions: str | None = None
    source: str = "manual"


# --- Session ---

class SessionMetadata(BaseModel):
    driver_name: str | None = None
    vehicle: VehicleInfo | None = None
    aero: AeroConfig | None = None
    tire_compound: str | None = None
    tire_pressures_cold: TirePressures | None = None
    tire_pressures_hot: TirePressures | None = None
    track_condition: TrackCondition = TrackCondition.DRY
    weather: WeatherData | None = None
    notes: str | None = None


class SessionCreate(BaseModel):
    metadata: SessionMetadata | None = None


class SessionResponse(BaseModel):
    id: str
    filename: str
    track_name: str | None = None
    venue: str | None = None
    session_date: datetime | None = None
    device_model: str | None = None
    num_laps: int
    best_lap_time_s: float | None = None
    best_lap_number: int | None = None
    metadata: SessionMetadata | None = None
    channels_available: list[str] = []
    created_at: datetime


# --- Lap ---

class LapSummary(BaseModel):
    lap_number: int
    lap_time_s: float
    delta_to_best_s: float
    max_speed_kph: float | None = None
    avg_lateral_g: float | None = None
    max_lateral_g: float | None = None
    max_braking_g: float | None = None


# --- Corner / Segment ---

class CornerInfo(BaseModel):
    corner_id: int
    name: str | None = None
    corner_type: str  # "left", "right"
    start_distance_m: float
    end_distance_m: float
    apex_distance_m: float


class CornerAnalysis(BaseModel):
    corner_id: int
    lap_number: int
    entry_speed_kph: float
    min_speed_kph: float
    exit_speed_kph: float
    max_lateral_g: float
    braking_start_distance_m: float | None = None
    throttle_start_distance_m: float | None = None
    time_in_corner_s: float


# --- Theoretical Best ---

class TheoreticalBest(BaseModel):
    actual_best_time_s: float
    theoretical_best_time_s: float
    time_delta_s: float
    improvement_pct: float
    segment_sources: list[dict]


# --- Consistency ---

class ConsistencyReport(BaseModel):
    overall_score_pct: float
    lap_time_std_s: float
    corner_scores: list[dict]
    most_consistent_corners: list[int]
    least_consistent_corners: list[int]


# --- G-G Diagram ---

class GGData(BaseModel):
    lateral_g: list[float]
    longitudinal_g: list[float]
    speed_kph: list[float] | None = None


# --- AI Coach ---

class CoachRecommendation(BaseModel):
    priority: str  # HIGH, MEDIUM, LOW
    category: str  # braking, throttle, line, consistency, setup
    corner_id: int | None = None
    description: str
    estimated_gain_s: float | None = None


class CoachingReport(BaseModel):
    session_id: str
    summary: str
    theoretical_best: TheoreticalBest | None = None
    recommendations: list[CoachRecommendation]
    overall_assessment: str


# --- Chat ---

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    conversation_history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    message: str
    tool_calls_made: list[str] = []


# --- Photo ---

class PhotoAnalyzeRequest(BaseModel):
    photo_type: PhotoType


class TirePhotoResult(BaseModel):
    compound: str | None = None
    wear_pattern: WearPattern | None = None
    wear_severity_pct: float | None = None
    heat_evidence: str | None = None
    condition_summary: str | None = None


class CarPhotoResult(BaseModel):
    aero_components: list[str] = []
    aero_level: AeroLevel = AeroLevel.NONE
    vehicle_type: str | None = None
    ride_height: str | None = None
    notable_features: list[str] = []
