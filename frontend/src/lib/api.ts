const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const OPENAI_KEY_STORAGE = "aim_openai_api_key";

export class DuplicateSessionError extends Error {
  existingSessionId: string;
  constructor(message: string, existingSessionId: string) {
    super(message);
    this.name = "DuplicateSessionError";
    this.existingSessionId = existingSessionId;
  }
}

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

// --- Sessions ---

export interface SessionResponse {
  id: string;
  filename: string;
  track_name: string | null;
  venue: string | null;
  session_date: string | null;
  device_model: string | null;
  num_laps: number;
  best_lap_time_s: number | null;
  best_lap_number: number | null;
  channels_available: string[];
  created_at: string;
  metadata: Record<string, unknown> | null;
}

export interface LapSummary {
  lap_number: number;
  lap_time_s: number;
  delta_to_best_s: number;
  max_speed_kph: number | null;
  avg_lateral_g: number | null;
  max_lateral_g: number | null;
  max_braking_g: number | null;
}

export async function uploadSession(file: File, metadata?: Record<string, unknown>): Promise<SessionResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (metadata) {
    formData.append("metadata_json", JSON.stringify(metadata));
  }

  const apiKey = getStoredApiKey();
  const headers: Record<string, string> = {};
  if (apiKey) headers["X-OpenAI-Key"] = apiKey;

  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (res.status === 409) {
    const body = await res.json();
    const detail = body.detail || {};
    throw new DuplicateSessionError(
      detail.message || "This file has already been uploaded",
      detail.existing_session_id || "",
    );
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json();
}

export async function listSessions(): Promise<SessionResponse[]> {
  return request<SessionResponse[]>("/api/sessions");
}

export async function getSession(id: string): Promise<SessionResponse> {
  return request<SessionResponse>(`/api/sessions/${id}`);
}

export async function deleteSession(id: string): Promise<void> {
  await request(`/api/sessions/${id}`, { method: "DELETE" });
}

export async function getLaps(sessionId: string): Promise<LapSummary[]> {
  return request<LapSummary[]>(`/api/sessions/${sessionId}/laps`);
}

// --- Analysis ---

export interface SpeedTrace {
  distance_m: number[];
  speed_kph: number[];
  time_ms: number[];
}

export async function getSpeedTraces(sessionId: string, lapNumbers: number[]): Promise<Record<string, SpeedTrace>> {
  return request(`/api/sessions/${sessionId}/analysis/speed-trace?lap_numbers=${lapNumbers.join(",")}`);
}

export interface GGData {
  lateral_g: number[];
  longitudinal_g: number[];
  speed_kph: number[] | null;
}

export async function getGGDiagram(sessionId: string, lapNumber: number): Promise<GGData> {
  return request(`/api/sessions/${sessionId}/analysis/gg-diagram?lap_number=${lapNumber}`);
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

export async function getTheoreticalBest(sessionId: string): Promise<TheoreticalBest> {
  return request(`/api/sessions/${sessionId}/analysis/theoretical-best`);
}

export interface ConsistencyReport {
  overall_score_pct: number;
  lap_time_std_s: number;
  corner_scores: Array<{ corner_id: number; consistency_score: number; std_s: number; mean_time_s: number }>;
  most_consistent_corners: number[];
  least_consistent_corners: number[];
}

export async function getConsistency(sessionId: string): Promise<ConsistencyReport> {
  return request(`/api/sessions/${sessionId}/analysis/consistency`);
}

export interface CornerInfo {
  corner_id: number;
  corner_type: string;
  start_distance_m: number;
  end_distance_m: number;
  apex_distance_m: number;
}

export async function getCorners(sessionId: string): Promise<CornerInfo[]> {
  return request(`/api/sessions/${sessionId}/analysis/corners`);
}

export interface CornerAnalysisData {
  corner_id: number;
  lap_number: number;
  entry_speed_kph: number;
  min_speed_kph: number;
  exit_speed_kph: number;
  max_lateral_g: number;
  time_in_corner_s: number;
  braking_start_distance_m: number | null;
  throttle_start_distance_m: number | null;
}

export async function getCornerAnalysis(sessionId: string, cornerId: number): Promise<CornerAnalysisData[]> {
  return request(`/api/sessions/${sessionId}/analysis/corners/${cornerId}`);
}

// --- Track Map ---

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

export async function getTrackMap(sessionId: string, lapNumber: number): Promise<TrackMapData> {
  return request(`/api/sessions/${sessionId}/analysis/track-map?lap_number=${lapNumber}`);
}

// --- Track Info ---

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

export async function getTrackInfo(sessionId: string): Promise<TrackInfo> {
  return request(`/api/sessions/${sessionId}/analysis/track-info`);
}

// --- Corner Suggestions ---

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

export async function getCornerSuggestions(sessionId: string): Promise<CornerSuggestionsResponse> {
  return request(`/api/sessions/${sessionId}/analysis/corner-suggestions`);
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

export async function compareLaps(sessionId: string, lapA: number, lapB: number): Promise<LapComparisonResult> {
  return request(`/api/sessions/${sessionId}/analysis/compare?lap_a=${lapA}&lap_b=${lapB}`);
}

export interface CrossSessionComparisonResult extends LapComparisonResult {
  session_a_id: string;
  session_b_id: string;
  session_a_name: string;
  session_b_name: string;
  session_a_date: string | null;
  session_b_date: string | null;
}

export async function compareLapsCrossSession(
  sessionA: string,
  lapA: number,
  sessionB: string,
  lapB: number,
): Promise<CrossSessionComparisonResult> {
  return request(`/api/compare?session_a=${sessionA}&lap_a=${lapA}&session_b=${sessionB}&lap_b=${lapB}`);
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

export async function getCompareCoaching(sessionId: string, lapA: number, lapB: number): Promise<ComparisonCoaching> {
  return request(`/api/sessions/${sessionId}/analysis/compare/coaching?lap_a=${lapA}&lap_b=${lapB}`, { method: "POST" });
}

export async function getCrossCompareCoaching(
  sessionA: string, lapA: number, sessionB: string, lapB: number,
): Promise<ComparisonCoaching> {
  return request(
    `/api/compare/coaching?session_a=${sessionA}&lap_a=${lapA}&session_b=${sessionB}&lap_b=${lapB}`,
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

export async function generateCoachingReport(sessionId: string): Promise<CoachingReport> {
  return request(`/api/sessions/${sessionId}/coaching-report`, { method: "POST" });
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
  sessionId: string,
  message: string,
  history: ChatMessage[] = [],
): Promise<ChatResponse> {
  return request(`/api/sessions/${sessionId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message, conversation_history: history }),
  });
}

export async function getChatHistory(sessionId: string): Promise<Array<{ role: string; content: string; created_at: string }>> {
  return request(`/api/sessions/${sessionId}/chat/history`);
}

// --- Photos ---

export async function uploadPhoto(
  sessionId: string,
  photoType: string,
  file: File,
): Promise<{ photo_type: string; analysis: Record<string, unknown> }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("photo_type", photoType);
  return request(`/api/sessions/${sessionId}/photos/analyze`, {
    method: "POST",
    body: formData,
  });
}

export async function listPhotos(sessionId: string): Promise<Array<{ id: string; photo_type: string; analysis: Record<string, unknown> }>> {
  return request(`/api/sessions/${sessionId}/photos`);
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
