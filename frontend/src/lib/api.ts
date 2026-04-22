const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const OPENAI_KEY_STORAGE = "aim_openai_api_key";

export function getStoredApiKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(OPENAI_KEY_STORAGE) || "";
}

export function setStoredApiKey(key: string) {
  if (typeof window === "undefined") return;
  if (key) {
    localStorage.setItem(OPENAI_KEY_STORAGE, key);
  } else {
    localStorage.removeItem(OPENAI_KEY_STORAGE);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const apiKey = getStoredApiKey();
  const headers: Record<string, string> = {};
  if (options?.headers) {
    Object.assign(headers, options.headers);
  }
  if (apiKey) {
    headers["X-OpenAI-Key"] = apiKey;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export async function validateApiKey(apiKey: string): Promise<{ valid: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/api/settings/validate-key`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  return res.json();
}

// --- Analysis (stateless) ---

export interface LapSummary {
  lap_number: number;
  lap_time_s: number;
  delta_to_best_s: number;
  max_speed_kph: number | null;
  avg_lateral_g: number | null;
  max_lateral_g: number | null;
  max_braking_g: number | null;
}

export interface SegmentSource {
  segment_start_m: number;
  segment_end_m: number;
  best_time_s: number;
  from_lap: number;
  type: "corner" | "straight" | "sector";
  label: string;
  corner_id: number | null;
  per_lap_times: Record<number, number>;
}

export interface TheoreticalBest {
  actual_best_time_s: number;
  theoretical_best_time_s: number;
  time_delta_s: number;
  improvement_pct: number;
  best_lap_number: number;
  segment_sources: SegmentSource[];
}

export interface ConsistencyReport {
  overall_score_pct: number;
  lap_time_std_s: number;
  corner_scores: Array<{ corner_id: number; consistency_score: number; std_s: number; mean_time_s: number }>;
  most_consistent_corners: number[];
  least_consistent_corners: number[];
}

export interface CornerSuggestion {
  corner_id: number;
  corner_label: string;
  category: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  suggestion: string;
  estimated_gain_s: number | null;
  data: Record<string, number>;
}

export interface CornerSuggestionsResponse {
  suggestions: CornerSuggestion[];
  total_estimated_gain_s: number;
  num_corners: number;
  track_name: string;
  summary: string;
}

export interface TrackCornerInfo {
  corner_id: number;
  corner_type: string;
  apex_distance_m: number;
  label: string;
  name: string;
  description: string;
}

export interface TrackInfo {
  track_name: string;
  track_matched: boolean;
  corners: TrackCornerInfo[];
}

export interface GripAssessment {
  rating: "good" | "reduced" | "poor";
  notes: string[];
}

export interface WeatherData {
  air_temp_f: number;
  air_temp_c: number;
  humidity_pct: number;
  wind_speed_mph: number;
  wind_speed_kmh: number;
  wind_direction_deg: number;
  wind_direction_label: string;
  precipitation_mm: number;
  surface_pressure_hpa: number;
  cloud_cover_pct: number;
  grip_assessment: GripAssessment;
  source: string;
  conditions_label: string;
}

export interface AnalysisResult {
  token: string;
  filename: string;
  track_name: string | null;
  session_date: string | null;
  device_model: string | null;
  num_laps: number;
  best_lap_time_s: number | null;
  best_lap_number: number | null;
  channels_available: string[];
  laps: LapSummary[];
  theoretical_best: TheoreticalBest | null;
  consistency: ConsistencyReport | null;
  corner_suggestions: CornerSuggestionsResponse | null;
  track_info: TrackInfo | null;
  weather: WeatherData | null;
}

export async function analyzeFile(file: File): Promise<AnalysisResult> {
  const formData = new FormData();
  formData.append("file", file);

  const apiKey = getStoredApiKey();
  const headers: Record<string, string> = {};
  if (apiKey) headers["X-OpenAI-Key"] = apiKey;

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json();
}

// --- Follow-up queries using token ---

export interface SpeedTrace {
  distance_m: number[];
  speed_kph: number[];
  time_ms: number[];
}

export async function getSpeedTraces(token: string, lapNumbers: number[]): Promise<Record<string, SpeedTrace>> {
  return request(`/api/analyze/${token}/speed-trace?lap_numbers=${lapNumbers.join(",")}`);
}

export interface GGData {
  lateral_g: number[];
  longitudinal_g: number[];
  speed_kph: number[] | null;
}

export async function getGGDiagram(token: string, lapNumber: number): Promise<GGData> {
  return request(`/api/analyze/${token}/gg-diagram?lap_number=${lapNumber}`);
}

export interface TrackMapPoint {
  lat: number;
  lon: number;
  speed_mph: number;
  distance_m: number;
  time_ms: number;
}

export interface TrackMapCorner {
  corner_id: number;
  corner_type: string;
  lat: number;
  lon: number;
  apex_distance_m: number;
  label: string;
  name: string;
  description?: string;
}

export interface TrackMapData {
  points: TrackMapPoint[];
  corners: TrackMapCorner[];
  min_speed: number;
  max_speed: number;
}

export async function getTrackMap(token: string, lapNumber: number): Promise<TrackMapData> {
  return request(`/api/analyze/${token}/track-map?lap_number=${lapNumber}`);
}

// --- Lap Comparison ---

export interface LapComparisonCornerDelta {
  corner_id: number;
  corner_label: string;
  corner_type: string;
  time_delta_s: number;
  lap_a: {
    entry_speed_mph: number;
    min_speed_mph: number;
    exit_speed_mph: number;
    time_s: number;
    max_lateral_g: number;
  };
  lap_b: {
    entry_speed_mph: number;
    min_speed_mph: number;
    exit_speed_mph: number;
    time_s: number;
    max_lateral_g: number;
  };
}

export interface LapComparisonDeltaPoint {
  distance_m: number;
  time_delta_s: number;
  speed_a_mph: number;
  speed_b_mph: number;
  speed_diff_mph: number;
  throttle_a?: number;
  throttle_b?: number;
  brake_a?: number;
  brake_b?: number;
  steer_a?: number;
  steer_b?: number;
}

export interface LapComparisonResult {
  lap_a: number;
  lap_b: number;
  lap_a_time_s: number;
  lap_b_time_s: number;
  total_delta_s: number;
  delta_trace: LapComparisonDeltaPoint[];
  corner_deltas: LapComparisonCornerDelta[];
  biggest_loss_corner: number | null;
  biggest_gain_corner: number | null;
  available_channels?: string[];
}

export async function compareLaps(token: string, lapA: number, lapB: number): Promise<LapComparisonResult> {
  return request(`/api/analyze/${token}/compare?lap_a=${lapA}&lap_b=${lapB}`);
}

export async function compareLapsCross(
  tokenA: string, lapA: number,
  tokenB: string, lapB: number,
): Promise<LapComparisonResult> {
  return request(`/api/analyze/compare-cross?token_a=${tokenA}&lap_a=${lapA}&token_b=${tokenB}&lap_b=${lapB}`);
}

// --- Comparison Coaching ---

export interface ComparisonCoachingFinding {
  corner_label: string;
  finding: string;
  impact: "positive" | "negative";
  time_impact_s: number;
  advice: string;
}

export interface PlainEnglishTip {
  tip: string;
  why: string;
  impact: "big" | "medium" | "small";
}

export interface ComparisonCoaching {
  headline: string;
  key_findings: ComparisonCoachingFinding[];
  progression_notes: string | null;
  action_items: string[];
  plain_english_tips?: PlainEnglishTip[];
}

export async function getCompareCoaching(token: string, lapA: number, lapB: number): Promise<ComparisonCoaching> {
  return request(`/api/analyze/${token}/compare/coaching?lap_a=${lapA}&lap_b=${lapB}`, { method: "POST" });
}

export async function getCrossCompareCoaching(
  tokenA: string, lapA: number,
  tokenB: string, lapB: number,
): Promise<ComparisonCoaching> {
  return request(
    `/api/analyze/compare-cross/coaching?token_a=${tokenA}&lap_a=${lapA}&token_b=${tokenB}&lap_b=${lapB}`,
    { method: "POST" },
  );
}

// --- AI Coach ---

export interface CoachingReport {
  summary: string;
  recommendations: Array<{
    priority: string;
    category: string;
    corner_id: number | null;
    description: string;
    estimated_gain_s: number | null;
  }>;
  overall_assessment: string;
}

export async function generateCoachingReport(token: string): Promise<CoachingReport> {
  return request(`/api/analyze/${token}/coaching-report`, { method: "POST" });
}

// --- Chat ---

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatResponse {
  message: string;
  tool_calls_made: string[];
}

export async function sendChatMessage(
  token: string,
  message: string,
  history: ChatMessage[] = [],
): Promise<ChatResponse> {
  return request(`/api/analyze/${token}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_history: history }),
  });
}

// --- Session Management ---

export async function clearSession(token: string): Promise<void> {
  await request(`/api/analyze/${token}`, { method: "DELETE" });
}

// --- Helpers ---

export function formatLapTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(3);
  return mins > 0 ? `${mins}:${secs.padStart(6, "0")}` : `${secs}s`;
}

export function formatDelta(seconds: number): string {
  const sign = seconds >= 0 ? "+" : "";
  const abs = Math.abs(seconds);
  if (abs >= 60) {
    const mins = Math.floor(abs / 60);
    const secs = (abs % 60).toFixed(3).padStart(6, "0");
    return `${sign}${mins}:${secs}`;
  }
  return `${sign}${abs.toFixed(3)}s`;
}

export function kphToMph(kph: number): number {
  return kph * 0.621371;
}
