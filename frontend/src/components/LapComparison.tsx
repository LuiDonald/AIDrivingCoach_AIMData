"use client";

import { useEffect, useState, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
} from "recharts";
import {
  compareLaps,
  compareLapsCrossSession,
  getCompareCoaching,
  getCrossCompareCoaching,
  listSessions,
  getLaps,
  LapComparisonResult,
  LapSummary,
  SessionResponse,
  ComparisonCoaching,
  formatLapTime,
  formatDelta,
} from "@/lib/api";

interface LapComparisonProps {
  sessionId: string;
  laps: LapSummary[];
  selectedLaps: number[];
  onSelectLaps: (laps: number[]) => void;
}

type CompareMode = "same" | "cross";

export default function LapComparison({
  sessionId,
  laps,
  selectedLaps,
  onSelectLaps,
}: LapComparisonProps) {
  const [result, setResult] = useState<LapComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<CompareMode>("same");
  const [view, setView] = useState<"delta" | "speed">("delta");

  // Same-session state
  const [lapA, setLapA] = useState<number | "">(selectedLaps[0] ?? "");
  const [lapB, setLapB] = useState<number | "">(selectedLaps[1] ?? "");

  // Cross-session state
  const [otherSessions, setOtherSessions] = useState<SessionResponse[]>([]);
  const [otherSessionId, setOtherSessionId] = useState<string>("");
  const [otherLaps, setOtherLaps] = useState<LapSummary[]>([]);
  const [otherLapNum, setOtherLapNum] = useState<number | "">(""  );
  const [loadingOtherLaps, setLoadingOtherLaps] = useState(false);
  const [crossLapA, setCrossLapA] = useState<number | "">(selectedLaps[0] ?? "");

  useEffect(() => {
    if (selectedLaps.length >= 2 && mode === "same") {
      setLapA(selectedLaps[0]);
      setLapB(selectedLaps[1]);
    }
  }, [selectedLaps, mode]);

  // Load other sessions for cross-session mode
  useEffect(() => {
    if (mode === "cross") {
      listSessions()
        .then((sessions) => {
          setOtherSessions(sessions.filter((s) => s.id !== sessionId));
        })
        .catch(console.error);
    }
  }, [mode, sessionId]);

  // Load laps for selected other session
  useEffect(() => {
    if (!otherSessionId) {
      setOtherLaps([]);
      return;
    }
    setLoadingOtherLaps(true);
    getLaps(otherSessionId)
      .then(setOtherLaps)
      .catch(console.error)
      .finally(() => setLoadingOtherLaps(false));
  }, [otherSessionId]);

  // Run same-session comparison
  useEffect(() => {
    if (mode !== "same" || lapA === "" || lapB === "" || lapA === lapB) {
      if (mode === "same") setResult(null);
      return;
    }
    setLoading(true);
    setError(null);
    compareLaps(sessionId, Number(lapA), Number(lapB))
      .then((r) => {
        setResult(r);
        onSelectLaps([Number(lapA), Number(lapB)]);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionId, lapA, lapB, mode]);

  // Run cross-session comparison
  const runCrossCompare = useCallback(() => {
    if (crossLapA === "" || otherLapNum === "" || !otherSessionId) return;
    setLoading(true);
    setError(null);
    compareLapsCrossSession(sessionId, Number(crossLapA), otherSessionId, Number(otherLapNum))
      .then((r) => {
        setResult(r);
        onSelectLaps([Number(crossLapA)]);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionId, crossLapA, otherSessionId, otherLapNum, onSelectLaps]);

  useEffect(() => {
    if (mode === "cross") {
      runCrossCompare();
    }
  }, [mode, crossLapA, otherLapNum, otherSessionId]);

  return (
    <div className="space-y-4">
      {/* Mode toggle */}
      <div className="flex gap-1 bg-gray-800/30 rounded-lg p-1">
        <button
          onClick={() => { setMode("same"); setResult(null); }}
          className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors touch-manipulation ${
            mode === "same" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Same Session
        </button>
        <button
          onClick={() => { setMode("cross"); setResult(null); }}
          className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors touch-manipulation ${
            mode === "cross" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Cross Session
        </button>
      </div>

      {/* Lap selectors */}
      <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/30">
        <h3 className="text-sm font-semibold text-white mb-3">
          {mode === "same" ? "Compare Two Laps" : "Compare Across Sessions"}
        </h3>

        {mode === "same" ? (
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <label className="text-[11px] text-gray-500 uppercase tracking-wider mb-1 block">
                Reference Lap (A)
              </label>
              <select
                value={lapA}
                onChange={(e) => setLapA(e.target.value === "" ? "" : Number(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">Select lap...</option>
                {laps.map((lap) => (
                  <option key={lap.lap_number} value={lap.lap_number}>
                    Lap {lap.lap_number} — {formatLapTime(lap.lap_time_s)}
                    {lap.delta_to_best_s === 0 ? " (BEST)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end pb-2 text-gray-500 font-bold text-lg">vs</div>
            <div className="flex-1">
              <label className="text-[11px] text-gray-500 uppercase tracking-wider mb-1 block">
                Comparison Lap (B)
              </label>
              <select
                value={lapB}
                onChange={(e) => setLapB(e.target.value === "" ? "" : Number(e.target.value))}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">Select lap...</option>
                {laps.map((lap) => (
                  <option key={lap.lap_number} value={lap.lap_number}>
                    Lap {lap.lap_number} — {formatLapTime(lap.lap_time_s)}
                    {lap.delta_to_best_s === 0 ? " (BEST)" : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Row 1: This session's lap */}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1">
                <label className="text-[11px] text-blue-400 uppercase tracking-wider mb-1 block">
                  This Session — Lap (A)
                </label>
                <select
                  value={crossLapA}
                  onChange={(e) => setCrossLapA(e.target.value === "" ? "" : Number(e.target.value))}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="">Select lap...</option>
                  {laps.map((lap) => (
                    <option key={lap.lap_number} value={lap.lap_number}>
                      Lap {lap.lap_number} — {formatLapTime(lap.lap_time_s)}
                      {lap.delta_to_best_s === 0 ? " (BEST)" : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end pb-2 text-gray-500 font-bold text-lg">vs</div>
              <div className="flex-1">
                <label className="text-[11px] text-orange-400 uppercase tracking-wider mb-1 block">
                  Other Session
                </label>
                <select
                  value={otherSessionId}
                  onChange={(e) => {
                    setOtherSessionId(e.target.value);
                    setOtherLapNum("");
                  }}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="">Select session...</option>
                  {otherSessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.track_name || s.filename}
                      {s.session_date
                        ? ` — ${new Date(s.session_date).toLocaleDateString()}`
                        : ""}
                      {s.best_lap_time_s
                        ? ` (${formatLapTime(s.best_lap_time_s)})`
                        : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Row 2: Other session's lap */}
            {otherSessionId && (
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1 sm:ml-[calc(50%+18px)]">
                  <label className="text-[11px] text-orange-400 uppercase tracking-wider mb-1 block">
                    Lap (B) from other session
                  </label>
                  {loadingOtherLaps ? (
                    <div className="text-xs text-gray-500 py-2">Loading laps...</div>
                  ) : (
                    <select
                      value={otherLapNum}
                      onChange={(e) => setOtherLapNum(e.target.value === "" ? "" : Number(e.target.value))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="">Select lap...</option>
                      {otherLaps.map((lap) => (
                        <option key={lap.lap_number} value={lap.lap_number}>
                          Lap {lap.lap_number} — {formatLapTime(lap.lap_time_s)}
                          {lap.delta_to_best_s === 0 ? " (BEST)" : ""}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-8 text-gray-400">
          <svg className="animate-spin w-5 h-5 mr-2 text-blue-500" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Comparing laps...
        </div>
      )}

      {error && <div className="text-red-400 text-sm text-center py-4">{error}</div>}

      {result && (
        <ComparisonResults
          result={result}
          view={view}
          setView={setView}
          mode={mode}
          sessionId={sessionId}
          otherSessionId={otherSessionId}
        />
      )}
    </div>
  );
}

function ComparisonResults({
  result,
  view,
  setView,
  mode,
  sessionId,
  otherSessionId,
}: {
  result: LapComparisonResult & { session_a_name?: string; session_b_name?: string; session_a_date?: string | null; session_b_date?: string | null };
  view: "delta" | "speed";
  setView: (v: "delta" | "speed") => void;
  mode: CompareMode;
  sessionId: string;
  otherSessionId: string;
}) {
  const [coaching, setCoaching] = useState<ComparisonCoaching | null>(null);
  const [coachLoading, setCoachLoading] = useState(false);
  const [coachError, setCoachError] = useState<string | null>(null);

  const requestCoaching = useCallback(async () => {
    setCoachLoading(true);
    setCoachError(null);
    try {
      let data: ComparisonCoaching;
      if (mode === "cross" && otherSessionId) {
        data = await getCrossCompareCoaching(sessionId, result.lap_a, otherSessionId, result.lap_b);
      } else {
        data = await getCompareCoaching(sessionId, result.lap_a, result.lap_b);
      }
      setCoaching(data);
    } catch (e) {
      setCoachError(e instanceof Error ? e.message : "Failed to get coaching analysis");
    } finally {
      setCoachLoading(false);
    }
  }, [mode, sessionId, otherSessionId, result.lap_a, result.lap_b]);

  const isCross = mode === "cross" && result.session_a_name;
  const labelA = isCross
    ? `Lap ${result.lap_a} — ${result.session_a_name}${result.session_a_date ? ` (${new Date(result.session_a_date).toLocaleDateString()})` : ""}`
    : `Lap ${result.lap_a}`;
  const labelB = isCross
    ? `Lap ${result.lap_b} — ${result.session_b_name}${result.session_b_date ? ` (${new Date(result.session_b_date).toLocaleDateString()})` : ""}`
    : `Lap ${result.lap_b}`;
  const shortA = `Lap ${result.lap_a}`;
  const shortB = isCross ? `Lap ${result.lap_b} (other)` : `Lap ${result.lap_b}`;

  return (
    <>
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-blue-500/10 rounded-xl p-3 border border-blue-500/20 text-center">
          <div className="text-[10px] text-blue-400 mb-0.5 truncate" title={labelA}>
            {isCross ? labelA : `Lap ${result.lap_a} (Ref)`}
          </div>
          <div className="text-lg font-mono font-bold text-blue-400">
            {formatLapTime(result.lap_a_time_s)}
          </div>
        </div>
        <div
          className={`rounded-xl p-3 border text-center ${
            result.total_delta_s > 0
              ? "bg-red-500/10 border-red-500/20"
              : "bg-green-500/10 border-green-500/20"
          }`}
        >
          <div className="text-[10px] text-gray-400 mb-0.5">Delta</div>
          <div
            className={`text-lg font-mono font-bold ${
              result.total_delta_s > 0 ? "text-red-400" : "text-green-400"
            }`}
          >
            {formatDelta(result.total_delta_s)}
          </div>
        </div>
        <div className="bg-orange-500/10 rounded-xl p-3 border border-orange-500/20 text-center">
          <div className="text-[10px] text-orange-400 mb-0.5 truncate" title={labelB}>
            {isCross ? labelB : `Lap ${result.lap_b}`}
          </div>
          <div className="text-lg font-mono font-bold text-orange-400">
            {formatLapTime(result.lap_b_time_s)}
          </div>
        </div>
      </div>

      {/* Chart toggle */}
      <div className="flex gap-1 bg-gray-800/30 rounded-lg p-1">
        <button
          onClick={() => setView("delta")}
          className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-colors touch-manipulation ${
            view === "delta" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Time Delta
        </button>
        <button
          onClick={() => setView("speed")}
          className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-colors touch-manipulation ${
            view === "speed" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Speed Overlay
        </button>
      </div>

      {/* Delta / Speed chart */}
      <div className="bg-gray-800/50 rounded-xl p-2 md:p-4 border border-gray-700/30">
        <ResponsiveContainer width="100%" height={240}>
          {view === "delta" ? (
            <ComposedChart data={result.delta_trace}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="distance_m" stroke="#6B7280" fontSize={11} tickFormatter={(v) => `${v}m`} />
              <YAxis
                stroke="#6B7280"
                fontSize={11}
                tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}s`}
                label={{ value: "Delta (s)", angle: -90, position: "insideLeft", fill: "#6B7280", fontSize: 10 }}
              />
              <ReferenceLine y={0} stroke="#6B7280" strokeDasharray="4 4" />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
                labelFormatter={(v) => `${v}m`}
                formatter={(value, name) => {
                  if (name === "time_delta_s_fill") return null;
                  const v = typeof value === "number" ? value : Number(value) || 0;
                  return [`${v > 0 ? "+" : ""}${v.toFixed(3)}s`, `${shortB} vs ${shortA}`];
                }}
              />
              <defs>
                <linearGradient id="deltaFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#EF4444" stopOpacity={0.3} />
                  <stop offset="50%" stopColor="#EF4444" stopOpacity={0} />
                  <stop offset="50%" stopColor="#10B981" stopOpacity={0} />
                  <stop offset="100%" stopColor="#10B981" stopOpacity={0.3} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="time_delta_s" fill="url(#deltaFill)" stroke="none" name="time_delta_s_fill" tooltipType="none" />
              <Line type="monotone" dataKey="time_delta_s" stroke="#F59E0B" strokeWidth={2} dot={false} />
            </ComposedChart>
          ) : (
            <LineChart data={result.delta_trace}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="distance_m" stroke="#6B7280" fontSize={11} tickFormatter={(v) => `${v}m`} />
              <YAxis
                stroke="#6B7280"
                fontSize={11}
                label={{ value: "mph", angle: -90, position: "insideLeft", fill: "#6B7280", fontSize: 10 }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
                labelFormatter={(v) => `${v}m`}
                formatter={(value, name) => [
                  `${typeof value === "number" ? value : Number(value) || 0} mph`,
                  name === "speed_a_mph" ? shortA : shortB,
                ]}
              />
              <Line type="monotone" dataKey="speed_a_mph" stroke="#3B82F6" strokeWidth={2} dot={false} name="speed_a_mph" />
              <Line type="monotone" dataKey="speed_b_mph" stroke="#F97316" strokeWidth={2} dot={false} name="speed_b_mph" />
            </LineChart>
          )}
        </ResponsiveContainer>
        <div className="flex justify-center gap-4 mt-1 text-[11px] text-gray-400">
          {view === "delta" ? (
            <>
              <span>Above zero = {shortB} slower</span>
              <span>Below zero = {shortB} faster</span>
            </>
          ) : (
            <>
              <span className="flex items-center gap-1">
                <span className="w-3 h-0.5 bg-blue-500 inline-block rounded" /> {shortA}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-0.5 bg-orange-500 inline-block rounded" /> {shortB}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Corner-by-corner table */}
      {result.corner_deltas.length > 0 && (
        <div className="bg-gray-800/50 rounded-xl border border-gray-700/30 overflow-hidden">
          <div className="px-4 py-3">
            <h4 className="text-sm font-semibold text-white">Corner-by-Corner Breakdown</h4>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-700/50 text-gray-500">
                  <th className="text-left px-4 py-2 font-medium">Corner</th>
                  <th className="text-right px-2 py-2 font-medium">Delta</th>
                  <th className="text-right px-2 py-2 font-medium">Entry A</th>
                  <th className="text-right px-2 py-2 font-medium">Entry B</th>
                  <th className="text-right px-2 py-2 font-medium">Apex A</th>
                  <th className="text-right px-2 py-2 font-medium">Apex B</th>
                  <th className="text-right px-2 py-2 font-medium">Exit A</th>
                  <th className="text-right px-4 py-2 font-medium">Exit B</th>
                </tr>
              </thead>
              <tbody>
                {result.corner_deltas.map((cd) => {
                  const isLoss = cd.time_delta_s > 0.01;
                  const isGain = cd.time_delta_s < -0.01;
                  const isBiggest =
                    cd.corner_id === result.biggest_loss_corner ||
                    cd.corner_id === result.biggest_gain_corner;
                  return (
                    <tr
                      key={cd.corner_id}
                      className={`border-b border-gray-700/20 ${isBiggest ? "bg-gray-700/20" : ""}`}
                    >
                      <td className="px-4 py-2 font-semibold text-gray-300 whitespace-nowrap">
                        {cd.corner_label}
                      </td>
                      <td
                        className={`text-right px-2 py-2 font-mono font-bold ${
                          isLoss ? "text-red-400" : isGain ? "text-green-400" : "text-gray-400"
                        }`}
                      >
                        {cd.time_delta_s > 0 ? "+" : ""}
                        {cd.time_delta_s.toFixed(3)}s
                      </td>
                      <td className="text-right px-2 py-2 text-blue-400 font-mono">{cd.lap_a.entry_speed_mph}</td>
                      <td className="text-right px-2 py-2 text-orange-400 font-mono">{cd.lap_b.entry_speed_mph}</td>
                      <td className="text-right px-2 py-2 text-blue-400 font-mono">{cd.lap_a.min_speed_mph}</td>
                      <td className="text-right px-2 py-2 text-orange-400 font-mono">{cd.lap_b.min_speed_mph}</td>
                      <td className="text-right px-2 py-2 text-blue-400 font-mono">{cd.lap_a.exit_speed_mph}</td>
                      <td className="text-right px-4 py-2 text-orange-400 font-mono">{cd.lap_b.exit_speed_mph}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 flex gap-4 text-[10px] text-gray-500">
            <span>All speeds in mph</span>
            <span className="text-blue-400">Blue = {shortA}</span>
            <span className="text-orange-400">Orange = {shortB}</span>
          </div>
        </div>
      )}

      {/* AI Coach Analysis */}
      <div className="bg-gray-800/50 rounded-xl border border-gray-700/30 overflow-hidden">
        <div className="px-4 py-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-white">AI Coach Analysis</h4>
          {!coaching && !coachLoading && (
            <button
              onClick={requestCoaching}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white text-xs font-semibold py-1.5 px-4 rounded-lg transition-all active:scale-95 touch-manipulation"
            >
              Analyze
            </button>
          )}
        </div>

        {coachLoading && (
          <div className="px-4 pb-4 flex items-center text-gray-400 text-sm">
            <svg className="animate-spin w-4 h-4 mr-2 text-blue-500" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            AI coach is analyzing the comparison...
          </div>
        )}

        {coachError && (
          <div className="px-4 pb-4 text-red-400 text-sm">{coachError}</div>
        )}

        {coaching && (
          <div className="px-4 pb-4 space-y-3">
            {/* Headline */}
            <div className="bg-gradient-to-r from-blue-600/10 to-purple-600/10 border border-blue-500/20 rounded-lg p-3">
              <p className="text-white text-sm font-medium">{String(coaching.headline ?? "")}</p>
            </div>

            {/* Key findings */}
            <div className="space-y-2">
              {coaching.key_findings.map((f, i) => (
                <div
                  key={i}
                  className={`rounded-lg p-3 border ${
                    f.impact === "positive"
                      ? "bg-green-500/5 border-green-500/20"
                      : "bg-red-500/5 border-red-500/20"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      f.impact === "positive"
                        ? "bg-green-500/20 text-green-400"
                        : "bg-red-500/20 text-red-400"
                    }`}>
                      {f.impact === "positive" ? "GAIN" : "LOSS"}
                    </span>
                    <span className="text-xs font-semibold text-gray-300">{f.corner_label}</span>
                    {f.time_impact_s !== 0 && (
                      <span className={`text-[10px] font-mono ml-auto ${
                        f.impact === "positive" ? "text-green-400" : "text-red-400"
                      }`}>
                        {f.time_impact_s > 0 ? "+" : ""}{f.time_impact_s.toFixed(2)}s
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-200 mb-1">{String(f.finding ?? "")}</p>
                  <p className="text-xs text-gray-400 italic">{String(f.advice ?? "")}</p>
                </div>
              ))}
            </div>

            {/* Progression notes */}
            {coaching.progression_notes && (
              <div className="bg-gray-700/30 rounded-lg p-3 border border-gray-600/30">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1 font-semibold">
                  {isCross ? "Progress Notes" : "Session Notes"}
                </p>
                <p className="text-sm text-gray-300">{String(coaching.progression_notes ?? "")}</p>
              </div>
            )}

            {/* Action items */}
            {coaching.action_items.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 font-semibold">
                  Action Items for Next Session
                </p>
                <div className="space-y-1.5">
                  {coaching.action_items.map((item, i) => {
                    const text = typeof item === "string" ? item : (item as Record<string, unknown>)?.item ?? JSON.stringify(item);
                    return (
                      <div key={i} className="flex items-start gap-2">
                        <span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5">
                          {i + 1}
                        </span>
                        <p className="text-sm text-gray-200">{String(text)}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {!coaching && !coachLoading && !coachError && (
          <div className="px-4 pb-4">
            <p className="text-xs text-gray-500">
              Get AI-powered coaching insights explaining why one lap is faster and what to work on.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
