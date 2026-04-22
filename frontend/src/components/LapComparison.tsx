"use client";

import { useEffect, useState, useCallback, useRef } from "react";
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
  compareLapsCross,
  getCompareCoaching,
  getCrossCompareCoaching,
  sendChatMessage,
  ChatMessage,
  LapComparisonResult,
  LapSummary,
  AnalysisResult,
  ComparisonCoaching,
  formatLapTime,
  formatDelta,
} from "@/lib/api";

type CompareMode = "same" | "cross";

interface LapComparisonProps {
  token: string;
  laps: LapSummary[];
  selectedLaps: number[];
  onSelectLaps: (laps: number[]) => void;
  onHoverDistance?: (distance_m: number | null) => void;
  otherSessions?: AnalysisResult[];
}

export default function LapComparison({
  token,
  laps,
  selectedLaps,
  onSelectLaps,
  onHoverDistance,
  otherSessions = [],
}: LapComparisonProps) {
  const [result, setResult] = useState<LapComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"delta" | "speed">("delta");

  const [mode, setMode] = useState<CompareMode>("same");
  const [lapA, setLapA] = useState<number | "">(selectedLaps[0] ?? "");
  const [lapB, setLapB] = useState<number | "">(selectedLaps[1] ?? "");

  // Cross-session state
  const [crossSessionIdx, setCrossSessionIdx] = useState(0);
  const [crossLapB, setCrossLapB] = useState<number | "">("");

  const crossSession = otherSessions[crossSessionIdx] ?? null;
  const crossLaps = crossSession?.laps ?? [];

  useEffect(() => {
    if (mode === "same" && selectedLaps.length >= 2) {
      setLapA(selectedLaps[0]);
      setLapB(selectedLaps[1]);
    }
  }, [selectedLaps, mode]);

  useEffect(() => {
    if (crossSession && crossLaps.length > 0 && crossLapB === "") {
      const best = crossLaps.reduce((a, b) => a.lap_time_s < b.lap_time_s ? a : b);
      setCrossLapB(best.lap_number);
    }
  }, [crossSession, crossLaps, crossLapB]);

  // Same-session compare
  useEffect(() => {
    if (mode !== "same") return;
    if (lapA === "" || lapB === "" || lapA === lapB) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError(null);
    compareLaps(token, Number(lapA), Number(lapB))
      .then((r) => {
        setResult(r);
        onSelectLaps([Number(lapA), Number(lapB)]);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token, lapA, lapB, mode]);

  // Cross-session compare
  useEffect(() => {
    if (mode !== "cross") return;
    if (lapA === "" || crossLapB === "" || !crossSession) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError(null);
    compareLapsCross(token, Number(lapA), crossSession.token, Number(crossLapB))
      .then((r) => setResult(r))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token, lapA, crossLapB, crossSession, mode]);

  const isCross = mode === "cross";
  const sessionLabelA = "This Session";
  const sessionLabelB = crossSession
    ? (crossSession.track_name || crossSession.filename || "Other Session")
    : "Other Session";

  const coachingToken = token;
  const coachingTokenB = isCross ? crossSession?.token : undefined;
  const effectiveLapB = isCross ? Number(crossLapB) : Number(lapB);

  return (
    <div className="space-y-4">
      {/* Mode toggle — only show if other sessions are available */}
      {otherSessions.length > 0 && (
        <div className="flex gap-1 bg-gray-800/30 rounded-lg p-1">
          <button
            onClick={() => { setMode("same"); setResult(null); }}
            className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-colors touch-manipulation ${
              mode === "same" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
            }`}
          >
            Same Session
          </button>
          <button
            onClick={() => { setMode("cross"); setResult(null); }}
            className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-colors touch-manipulation ${
              mode === "cross" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
            }`}
          >
            Cross Session
          </button>
        </div>
      )}

      {/* Lap selectors */}
      <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/30">
        <h3 className="text-sm font-semibold text-white mb-3">
          {isCross ? "Compare Across Sessions" : "Compare Two Laps"}
        </h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="text-[11px] text-gray-500 uppercase tracking-wider mb-1 block">
              {isCross ? `Reference Lap (${sessionLabelA})` : "Reference Lap (A)"}
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
            {isCross && otherSessions.length > 0 && (
              <div className="mb-2">
                <label className="text-[11px] text-gray-500 uppercase tracking-wider mb-1 block">
                  Other Session
                </label>
                <select
                  value={crossSessionIdx}
                  onChange={(e) => {
                    const idx = Number(e.target.value);
                    setCrossSessionIdx(idx);
                    setCrossLapB("");
                  }}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  {otherSessions.map((s, i) => (
                    <option key={s.token} value={i}>
                      {s.track_name || s.filename}
                      {s.best_lap_time_s ? ` — ${formatLapTime(s.best_lap_time_s)}` : ""}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <label className="text-[11px] text-gray-500 uppercase tracking-wider mb-1 block">
              {isCross ? `Comparison Lap (${sessionLabelB})` : "Comparison Lap (B)"}
            </label>
            <select
              value={isCross ? crossLapB : lapB}
              onChange={(e) => {
                const v = e.target.value === "" ? "" as const : Number(e.target.value);
                if (isCross) setCrossLapB(v);
                else setLapB(v);
              }}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select lap...</option>
              {(isCross ? crossLaps : laps).map((lap) => (
                <option key={lap.lap_number} value={lap.lap_number}>
                  Lap {lap.lap_number} — {formatLapTime(lap.lap_time_s)}
                  {lap.delta_to_best_s === 0 ? " (BEST)" : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
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
          token={coachingToken}
          tokenB={coachingTokenB}
          isCross={isCross}
          labelA={isCross ? `${sessionLabelA} Lap ${lapA}` : `Lap ${result.lap_a}`}
          labelB={isCross ? `${sessionLabelB} Lap ${crossLapB}` : `Lap ${result.lap_b}`}
          onHoverDistance={onHoverDistance}
        />
      )}
    </div>
  );
}

function ComparisonResults({
  result,
  view,
  setView,
  token,
  tokenB,
  isCross,
  labelA,
  labelB,
  onHoverDistance,
}: {
  result: LapComparisonResult;
  view: "delta" | "speed";
  setView: (v: "delta" | "speed") => void;
  token: string;
  tokenB?: string;
  isCross: boolean;
  labelA: string;
  labelB: string;
  onHoverDistance?: (distance_m: number | null) => void;
}) {
  const [coaching, setCoaching] = useState<ComparisonCoaching | null>(null);
  const [coachLoading, setCoachLoading] = useState(false);
  const [coachError, setCoachError] = useState<string | null>(null);

  const handleChartHover = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (state: any) => {
      if (!onHoverDistance || !state?.isTooltipActive) {
        onHoverDistance?.(null);
        return;
      }
      const distance =
        state?.activePayload?.[0]?.payload?.distance_m
        ?? (typeof state?.activeLabel === "number" ? state.activeLabel : Number(state?.activeLabel));
      onHoverDistance(distance != null && !isNaN(distance) ? distance : null);
    },
    [onHoverDistance],
  );

  const handleChartLeave = useCallback(() => {
    onHoverDistance?.(null);
  }, [onHoverDistance]);

  const requestCoaching = useCallback(async () => {
    setCoachLoading(true);
    setCoachError(null);
    try {
      let data: ComparisonCoaching;
      if (isCross && tokenB) {
        data = await getCrossCompareCoaching(token, result.lap_a, tokenB, result.lap_b);
      } else {
        data = await getCompareCoaching(token, result.lap_a, result.lap_b);
      }
      setCoaching(data);
    } catch (e) {
      setCoachError(e instanceof Error ? e.message : "Failed to get coaching analysis");
    } finally {
      setCoachLoading(false);
    }
  }, [token, tokenB, isCross, result.lap_a, result.lap_b]);

  const shortA = labelA;
  const shortB = labelB;

  const firstPt = result.delta_trace[0] ?? {};
  const hasChannel = (base: string) => ({
    a: base + "_a" in firstPt,
    b: base + "_b" in firstPt,
    both: (base + "_a" in firstPt) && (base + "_b" in firstPt),
  });

  return (
    <>
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-blue-500/10 rounded-xl p-3 border border-blue-500/20 text-center">
          <div className="text-[10px] text-blue-400 mb-0.5 truncate" title={labelA}>
            {`${shortA} (Ref)`}
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
            {shortB}
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
            <ComposedChart data={result.delta_trace} onMouseMove={handleChartHover} onMouseLeave={handleChartLeave}>
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
            <LineChart data={result.delta_trace} onMouseMove={handleChartHover} onMouseLeave={handleChartLeave}>
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

      {/* Throttle overlay chart */}
      {result.available_channels?.includes("throttle") && (
        <div className="bg-gray-800/50 rounded-xl p-2 md:p-4 border border-gray-700/30">
          <h4 className="text-xs font-semibold text-gray-400 mb-1 px-1">Throttle %</h4>
          {!hasChannel("throttle").both && (
            <p className="text-[10px] text-amber-400/70 px-1 mb-1">
              Only {hasChannel("throttle").a ? shortA : shortB} has throttle data
            </p>
          )}
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={result.delta_trace} onMouseMove={handleChartHover} onMouseLeave={handleChartLeave}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="distance_m" stroke="#6B7280" fontSize={10} tickFormatter={(v) => `${v}m`} />
              <YAxis stroke="#6B7280" fontSize={10} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
                labelFormatter={(v) => `${v}m`}
                formatter={(value: number, name: string) => [
                  `${value}%`,
                  name === "throttle_a" ? shortA : shortB,
                ]}
              />
              {hasChannel("throttle").a && <Line type="monotone" dataKey="throttle_a" stroke="#3B82F6" strokeWidth={1.5} dot={false} name="throttle_a" />}
              {hasChannel("throttle").b && <Line type="monotone" dataKey="throttle_b" stroke="#F97316" strokeWidth={1.5} dot={false} name="throttle_b" />}
            </LineChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-1 text-[10px] text-gray-500">
            {hasChannel("throttle").a && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-500 inline-block rounded" /> {shortA}</span>}
            {hasChannel("throttle").b && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-orange-500 inline-block rounded" /> {shortB}</span>}
          </div>
        </div>
      )}

      {/* Brake overlay chart */}
      {result.available_channels?.includes("brake") && (
        <div className="bg-gray-800/50 rounded-xl p-2 md:p-4 border border-gray-700/30">
          <h4 className="text-xs font-semibold text-gray-400 mb-1 px-1">Brake Pressure</h4>
          {!hasChannel("brake").both && (
            <p className="text-[10px] text-amber-400/70 px-1 mb-1">
              Only {hasChannel("brake").a ? shortA : shortB} has brake data
            </p>
          )}
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={result.delta_trace} onMouseMove={handleChartHover} onMouseLeave={handleChartLeave}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="distance_m" stroke="#6B7280" fontSize={10} tickFormatter={(v) => `${v}m`} />
              <YAxis stroke="#6B7280" fontSize={10} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
                labelFormatter={(v) => `${v}m`}
                formatter={(value: number, name: string) => [
                  `${value}`,
                  name === "brake_a" ? shortA : shortB,
                ]}
              />
              {hasChannel("brake").a && <Line type="monotone" dataKey="brake_a" stroke="#3B82F6" strokeWidth={1.5} dot={false} name="brake_a" />}
              {hasChannel("brake").b && <Line type="monotone" dataKey="brake_b" stroke="#F97316" strokeWidth={1.5} dot={false} name="brake_b" />}
            </LineChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-1 text-[10px] text-gray-500">
            {hasChannel("brake").a && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-500 inline-block rounded" /> {shortA}</span>}
            {hasChannel("brake").b && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-orange-500 inline-block rounded" /> {shortB}</span>}
          </div>
        </div>
      )}

      {/* Steering angle overlay chart */}
      {result.available_channels?.includes("steering") && (
        <div className="bg-gray-800/50 rounded-xl p-2 md:p-4 border border-gray-700/30">
          <h4 className="text-xs font-semibold text-gray-400 mb-1 px-1">Steering Angle (deg)</h4>
          {!hasChannel("steer").both && (
            <p className="text-[10px] text-amber-400/70 px-1 mb-1">
              Only {hasChannel("steer").a ? shortA : shortB} has steering data
            </p>
          )}
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={result.delta_trace} onMouseMove={handleChartHover} onMouseLeave={handleChartLeave}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="distance_m" stroke="#6B7280" fontSize={10} tickFormatter={(v) => `${v}m`} />
              <YAxis stroke="#6B7280" fontSize={10} tickFormatter={(v) => `${v}°`} />
              <ReferenceLine y={0} stroke="#6B7280" strokeDasharray="4 4" />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
                labelFormatter={(v) => `${v}m`}
                formatter={(value: number, name: string) => [
                  `${value}°`,
                  name === "steer_a" ? shortA : shortB,
                ]}
              />
              {hasChannel("steer").a && <Line type="monotone" dataKey="steer_a" stroke="#3B82F6" strokeWidth={1.5} dot={false} name="steer_a" />}
              {hasChannel("steer").b && <Line type="monotone" dataKey="steer_b" stroke="#F97316" strokeWidth={1.5} dot={false} name="steer_b" />}
            </LineChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-1 text-[10px] text-gray-500">
            {hasChannel("steer").a && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-500 inline-block rounded" /> {shortA}</span>}
            {hasChannel("steer").b && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-orange-500 inline-block rounded" /> {shortB}</span>}
          </div>
        </div>
      )}

      {/* Yaw rate overlay chart */}
      {result.available_channels?.includes("yaw") && (
        <div className="bg-gray-800/50 rounded-xl p-2 md:p-4 border border-gray-700/30">
          <h4 className="text-xs font-semibold text-gray-400 mb-1 px-1">Yaw Rate (deg/s)</h4>
          {!hasChannel("yaw").both && (
            <p className="text-[10px] text-amber-400/70 px-1 mb-1">
              Only {hasChannel("yaw").a ? shortA : shortB} has yaw data
            </p>
          )}
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={result.delta_trace} onMouseMove={handleChartHover} onMouseLeave={handleChartLeave}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="distance_m" stroke="#6B7280" fontSize={10} tickFormatter={(v) => `${v}m`} />
              <YAxis stroke="#6B7280" fontSize={10} tickFormatter={(v) => `${v}°/s`} />
              <ReferenceLine y={0} stroke="#6B7280" strokeDasharray="4 4" />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
                labelFormatter={(v) => `${v}m`}
                formatter={(value: number, name: string) => [
                  `${value}°/s`,
                  name === "yaw_a" ? shortA : shortB,
                ]}
              />
              {hasChannel("yaw").a && <Line type="monotone" dataKey="yaw_a" stroke="#3B82F6" strokeWidth={1.5} dot={false} name="yaw_a" />}
              {hasChannel("yaw").b && <Line type="monotone" dataKey="yaw_b" stroke="#F97316" strokeWidth={1.5} dot={false} name="yaw_b" />}
            </LineChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-1 text-[10px] text-gray-500">
            {hasChannel("yaw").a && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-500 inline-block rounded" /> {shortA}</span>}
            {hasChannel("yaw").b && <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-orange-500 inline-block rounded" /> {shortB}</span>}
          </div>
        </div>
      )}

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
                  Session Notes
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

            {/* Plain English Tips */}
            {coaching.plain_english_tips && coaching.plain_english_tips.length > 0 && (
              <div className="mt-2 pt-3 border-t border-gray-700/40">
                <p className="text-xs text-amber-400/80 uppercase tracking-wider mb-2 font-semibold flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  Quick Tips — In Plain English
                </p>
                <div className="space-y-2">
                  {coaching.plain_english_tips.map((t, i) => {
                    const impactColor = t.impact === "big"
                      ? "bg-red-500/20 text-red-300 border-red-500/30"
                      : t.impact === "medium"
                        ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                        : "bg-gray-600/20 text-gray-400 border-gray-600/30";
                    return (
                      <div key={i} className="bg-gray-700/20 rounded-lg p-3 border border-gray-600/20">
                        <div className="flex items-start gap-2">
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border flex-shrink-0 mt-0.5 ${impactColor}`}>
                            {t.impact === "big" ? "BIG" : t.impact === "medium" ? "MED" : "SMALL"}
                          </span>
                          <div>
                            <p className="text-sm text-white font-medium">{String(t.tip)}</p>
                            <p className="text-xs text-gray-400 mt-0.5">{String(t.why)}</p>
                          </div>
                        </div>
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

      {/* Inline follow-up chat — appears after coaching analysis */}
      {coaching && (
        <CoachingChat
          token={token}
          coaching={coaching}
          lapA={result.lap_a}
          lapB={result.lap_b}
          labelA={shortA}
          labelB={shortB}
        />
      )}
    </>
  );
}


function CoachingChat({
  token,
  coaching,
  lapA,
  lapB,
  labelA,
  labelB,
}: {
  token: string;
  coaching: ComparisonCoaching;
  lapA: number;
  lapB: number;
  labelA: string;
  labelB: string;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const contextSeed: ChatMessage[] = [
    {
      role: "user",
      content: `I just compared ${labelA} vs ${labelB}. Here is the AI coaching analysis:\n\nHeadline: ${coaching.headline}\n\nKey findings:\n${coaching.key_findings.map((f) => `- ${f.corner_label}: ${f.finding} (${f.advice})`).join("\n")}\n\nPlain english tips:\n${(coaching.plain_english_tips || []).map((t) => `- ${t.tip}: ${t.why}`).join("\n")}\n\nI have follow-up questions about this analysis.`,
    },
    {
      role: "assistant",
      content: "I've reviewed the comparison analysis. What would you like to know more about? I can dig deeper into any specific corner, explain why something is happening, or suggest drills to improve.",
    },
  ];

  const send = async (text: string) => {
    if (!text.trim() || sending) return;
    const userMsg: ChatMessage = { role: "user", content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput("");
    setSending(true);

    try {
      const fullHistory = [...contextSeed, ...updated];
      const resp = await sendChatMessage(token, text, fullHistory.slice(0, -1));
      setMessages([...updated, { role: "assistant", content: resp.message }]);
    } catch {
      setMessages([
        ...updated,
        { role: "assistant", content: "Sorry, I had trouble processing that. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const quickQuestions = [
    "Which turn number is the biggest time loss?",
    "What should I focus on first?",
    "Am I at the limit or is there more grip?",
    "Is this a car setup issue or driving?",
  ];

  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700/30 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-700/30">
        <h4 className="text-sm font-semibold text-white flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          Ask Follow-up Questions
        </h4>
        <p className="text-[11px] text-gray-500 mt-0.5">Continue the conversation about this comparison</p>
      </div>

      <div className="max-h-[400px] overflow-y-auto">
        {messages.length === 0 && (
          <div className="px-4 pt-3 pb-1 flex flex-wrap gap-1.5">
            {quickQuestions.map((q) => (
              <button
                key={q}
                onClick={() => send(q)}
                className="text-[11px] bg-gray-700/50 text-blue-400 border border-gray-600/40 rounded-full px-3 py-1.5 hover:bg-gray-700 transition-colors touch-manipulation"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <div className="px-4 py-3 space-y-2.5">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-md"
                    : "bg-gray-700/60 text-gray-200 rounded-bl-md"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="bg-gray-700/60 rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex gap-1">
                  <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="px-3 py-2.5 border-t border-gray-700/30">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a specific corner, technique, or finding..."
            className="flex-1 bg-gray-700/60 text-white rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 placeholder-gray-500"
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-xl px-3.5 py-2.5 transition-colors active:scale-95 touch-manipulation"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
