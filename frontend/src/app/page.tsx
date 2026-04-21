"use client";

import { useState, useCallback } from "react";
import { analyzeFile, AnalysisResult, formatLapTime } from "@/lib/api";
import LapTable from "@/components/LapTable";
import SpeedTraceChart from "@/components/SpeedTraceChart";
import TrackMap from "@/components/TrackMap";
import CornerSuggestions from "@/components/CornerSuggestions";
import LapComparison from "@/components/LapComparison";
import CoachingPanel from "@/components/CoachingPanel";
import ChatPanel from "@/components/ChatPanel";
import TheoreticalBestBreakdown from "@/components/TheoreticalBestBreakdown";
import WeatherCard from "@/components/WeatherCard";

const SUPPORTED_EXTENSIONS = ["xrk", "xrz", "csv"];

type Tab = "overview" | "compare" | "coach";

export default function Home() {
  const [sessions, setSessions] = useState<AnalysisResult[]>([]);
  const [activeSessionIdx, setActiveSessionIdx] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState("");

  const [selectedLaps, setSelectedLaps] = useState<number[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [mapCollapsed, setMapCollapsed] = useState(false);
  const [hoverDistance, setHoverDistance] = useState<number | null>(null);
  const [hoverSectorRange, setHoverSectorRange] = useState<[number, number] | null>(null);

  const analysis = sessions[activeSessionIdx] ?? null;

  const handleFiles = useCallback(async (files: File[]) => {
    const valid = files.filter((f) => {
      const ext = f.name.split(".").pop()?.toLowerCase();
      return ext && SUPPORTED_EXTENSIONS.includes(ext);
    });
    if (valid.length === 0) {
      setError("No supported files found. Use .xrk, .xrz, or .csv files.");
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setProgress(`Uploading and analyzing ${valid.length} file${valid.length > 1 ? "s" : ""}...`);

    try {
      const results = await Promise.all(valid.map((f) => analyzeFile(f)));
      setSessions((prev) => {
        const next = [...prev, ...results];
        setActiveSessionIdx(next.length - results.length);
        return next;
      });
      const first = results[0];
      if (first?.best_lap_number) {
        setSelectedLaps([first.best_lap_number]);
      }
      setActiveTab("overview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setIsAnalyzing(false);
      setProgress("");
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) handleFiles(files);
    },
    [handleFiles],
  );

  const handleReset = () => {
    setSessions([]);
    setActiveSessionIdx(0);
    setSelectedLaps([]);
    setActiveTab("overview");
    setError(null);
  };

  const removeSession = (idx: number) => {
    setSessions((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      if (next.length === 0) {
        handleReset();
        return [];
      }
      setActiveSessionIdx((cur) => {
        if (cur >= next.length) return next.length - 1;
        if (cur > idx) return cur - 1;
        return cur;
      });
      return next;
    });
  };

  const switchSession = (idx: number) => {
    setActiveSessionIdx(idx);
    const s = sessions[idx];
    if (s?.best_lap_number) {
      setSelectedLaps([s.best_lap_number]);
    } else {
      setSelectedLaps([]);
    }
  };

  const toggleLap = (lap: number) => {
    setSelectedLaps((prev) =>
      prev.includes(lap) ? prev.filter((l) => l !== lap) : [...prev, lap],
    );
  };

  // ---- Landing / Upload View ----
  if (sessions.length === 0) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-lg text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
            AIM Analyzer
          </h1>
          <p className="text-gray-400 text-sm md:text-base">
            AI-powered motorsport telemetry analysis
          </p>
        </div>

        <div className="w-full max-w-lg mx-auto">
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-2xl p-8 md:p-12 text-center transition-all ${
              isDragging
                ? "border-blue-500 bg-blue-500/10"
                : "border-gray-600 hover:border-gray-400"
            } ${isAnalyzing ? "opacity-60 pointer-events-none" : ""}`}
          >
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-blue-500/20 flex items-center justify-center">
                <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>

              <div>
                <p className="text-lg font-semibold text-white">
                  {isAnalyzing ? progress : "Drop Your Telemetry Files"}
                </p>
                <p className="text-sm text-gray-400 mt-1">
                  AIM SOLO, Porsche Track Precision, or exported CSV
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  You can upload multiple files to compare across sessions
                </p>
              </div>

              {!isAnalyzing && (
                <label className="cursor-pointer bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-8 rounded-xl text-base transition-colors active:scale-95 touch-manipulation">
                  <input
                    type="file"
                    accept=".xrk,.xrz,.csv"
                    multiple
                    className="hidden"
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      if (files.length > 0) handleFiles(files);
                      e.target.value = "";
                    }}
                  />
                  Choose Files
                </label>
              )}

              {isAnalyzing && (
                <div className="flex items-center gap-2 text-blue-400">
                  <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span className="text-sm">Processing...</span>
                </div>
              )}

              <p className="text-xs text-gray-500 hidden md:block">
                or drag and drop your files here
              </p>
            </div>
          </div>

          {error && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="mt-12 text-center">
          <p className="text-xs text-gray-600 max-w-md">
            Your data is analyzed in memory and never stored.
            Close the tab and it&apos;s gone. No account needed.
          </p>
        </div>
      </div>
    );
  }

  if (!analysis) return null;

  const downloadReport = () => {
    const report = {
      exported_at: new Date().toISOString(),
      filename: analysis.filename,
      track_name: analysis.track_name,
      session_date: analysis.session_date,
      device_model: analysis.device_model,
      best_lap_time_s: analysis.best_lap_time_s,
      best_lap_number: analysis.best_lap_number,
      laps: analysis.laps,
      theoretical_best: analysis.theoretical_best,
      consistency: analysis.consistency,
      corner_suggestions: analysis.corner_suggestions,
      track_info: analysis.track_info,
      weather: analysis.weather,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(analysis.track_name || analysis.filename || "analysis").replace(/[^a-zA-Z0-9]/g, "_")}_report.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ---- Analysis Dashboard ----
  const { theoretical_best: theoretical, consistency, laps, corner_suggestions } = analysis;
  const activeLap = selectedLaps.length > 0 ? selectedLaps[0] : (analysis.best_lap_number || null);

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "compare", label: "Compare" },
    { key: "coach", label: "AI Coach" },
  ];

  const trackMapSidebar = (
    <div className="space-y-3">
      {hoverDistance != null && (
        <div className="bg-amber-500/20 border border-amber-500/40 rounded-lg px-3 py-1.5 text-xs text-amber-300 font-mono text-center">
          Chart hover: {hoverDistance.toFixed(1)}m
        </div>
      )}
      <TrackMap
        token={analysis.token}
        lapNumber={activeLap}
        highlightDistance={hoverDistance}
        highlightRange={hoverSectorRange}
      />
    </div>
  );

  const sessionLabel = (s: AnalysisResult) =>
    s.track_name || s.filename || "Unknown";

  return (
    <div className="max-w-7xl mx-auto px-4 py-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <button
            onClick={handleReset}
            className="text-xs text-gray-500 hover:text-gray-300 mb-1 block"
          >
            &larr; New Analysis
          </button>
          <h1 className="text-xl md:text-2xl font-bold text-white">
            {analysis.track_name || analysis.filename}
          </h1>
          <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-400">
            {analysis.session_date && (
              <span>{new Date(analysis.session_date).toLocaleDateString()}</span>
            )}
            <span>{analysis.num_laps} laps</span>
            {analysis.device_model && <span>{analysis.device_model}</span>}
          </div>
        </div>
        <div className="flex items-start gap-3 flex-shrink-0">
          {analysis.best_lap_time_s && (
            <div className="text-right">
              <div className="text-2xl font-mono font-bold text-green-400">
                {formatLapTime(analysis.best_lap_time_s)}
              </div>
              <div className="text-xs text-gray-500">best lap</div>
            </div>
          )}
          <button
            onClick={downloadReport}
            className="p-2 rounded-lg bg-gray-800/80 hover:bg-gray-700 border border-gray-700 transition-colors group"
            title="Download Report (JSON)"
          >
            <svg className="w-5 h-5 text-gray-400 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Session tabs (when multiple files are loaded) */}
      {sessions.length > 1 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {sessions.map((s, i) => (
              <button
                key={s.token}
                onClick={() => switchSession(i)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  i === activeSessionIdx
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/40"
                    : "bg-gray-800/50 text-gray-400 border border-gray-700/30 hover:text-white hover:border-gray-600"
                }`}
              >
                <span className="truncate max-w-[140px]">{sessionLabel(s)}</span>
                {s.best_lap_time_s && (
                  <span className="text-[10px] font-mono opacity-70">
                    {formatLapTime(s.best_lap_time_s)}
                  </span>
                )}
                <span
                  onClick={(e) => { e.stopPropagation(); removeSession(i); }}
                  className="ml-1 text-gray-500 hover:text-red-400 transition-colors"
                  title="Remove this session"
                >
                  &times;
                </span>
              </button>
            ))}
            <label className="cursor-pointer flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800/50 text-gray-500 border border-dashed border-gray-600 hover:text-white hover:border-gray-400 transition-colors whitespace-nowrap">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add File
              <input
                type="file"
                accept=".xrk,.xrz,.csv"
                multiple
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files || []);
                  if (files.length > 0) handleFiles(files);
                  e.target.value = "";
                }}
              />
            </label>
          </div>
        </div>
      )}

      {/* Add more files button (single session) */}
      {sessions.length === 1 && (
        <div className="mb-4">
          <label className="cursor-pointer inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800/50 text-gray-500 border border-dashed border-gray-600 hover:text-white hover:border-gray-400 transition-colors">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add More Files to Compare
            <input
              type="file"
              accept=".xrk,.xrz,.csv"
              multiple
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files || []);
                if (files.length > 0) handleFiles(files);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        {theoretical && (
          <>
            <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700/30">
              <div className="text-xs text-gray-500 mb-1">Theoretical Best</div>
              <div className="text-lg font-mono font-bold text-blue-400">
                {formatLapTime(theoretical.theoretical_best_time_s)}
              </div>
            </div>
            <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700/30">
              <div className="text-xs text-gray-500 mb-1">Time Left on Table</div>
              <div className="text-lg font-mono font-bold text-yellow-400">
                {theoretical.time_delta_s.toFixed(3)}s
              </div>
              <div className="text-xs text-gray-500">{theoretical.improvement_pct.toFixed(1)}%</div>
            </div>
          </>
        )}
        {consistency && (
          <>
            <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700/30">
              <div className="text-xs text-gray-500 mb-1">Consistency</div>
              <div className={`text-lg font-bold ${
                consistency.overall_score_pct >= 80
                  ? "text-green-400"
                  : consistency.overall_score_pct >= 60
                  ? "text-yellow-400"
                  : "text-red-400"
              }`}>
                {consistency.overall_score_pct.toFixed(0)}%
              </div>
            </div>
            <div className="bg-gray-800/50 rounded-xl p-3 border border-gray-700/30">
              <div className="text-xs text-gray-500 mb-1">Lap Variation</div>
              <div className="text-lg font-mono font-bold text-gray-300">
                {consistency.lap_time_std_s > 0 ? `\u00B1${consistency.lap_time_std_s.toFixed(2)}s` : "N/A"}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Mobile: collapsible track map */}
      <div className="lg:hidden mb-4">
        <button
          onClick={() => setMapCollapsed(!mapCollapsed)}
          className="w-full flex items-center justify-between bg-gray-800/50 rounded-xl px-4 py-2.5 border border-gray-700/30 text-sm text-gray-300 touch-manipulation"
        >
          <span className="font-semibold">Track Map</span>
          <svg
            className={`w-4 h-4 transition-transform ${mapCollapsed ? "" : "rotate-180"}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {!mapCollapsed && <div className="mt-2">{trackMapSidebar}</div>}
      </div>

      {/* Two-column layout */}
      <div className="flex gap-4">
        <div className="flex-1 min-w-0">
          {/* Tab bar */}
          <div className="flex gap-1 bg-gray-800/30 rounded-xl p-1 mb-4 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => { setActiveTab(tab.key); setHoverDistance(null); }}
                className={`flex-1 min-w-0 py-2.5 px-3 rounded-lg text-sm font-medium transition-colors touch-manipulation whitespace-nowrap ${
                  activeTab === tab.key
                    ? "bg-gray-700 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className={activeTab === "overview" ? "" : "hidden"}>
            <div className="space-y-6">
              {analysis.weather && <WeatherCard weather={analysis.weather} />}
              {theoretical && theoretical.segment_sources.length > 0 && (
                <TheoreticalBestBreakdown theoretical={theoretical} laps={laps} onHoverSector={setHoverSectorRange} />
              )}
              <LapTable laps={laps} selectedLaps={selectedLaps} onToggleLap={toggleLap} />
              <SpeedTraceChart token={analysis.token} lapNumbers={selectedLaps} />
            </div>
          </div>

          <div className={activeTab === "compare" ? "" : "hidden"}>
            <LapComparison
              token={analysis.token}
              laps={laps}
              selectedLaps={selectedLaps}
              onSelectLaps={setSelectedLaps}
              onHoverDistance={setHoverDistance}
              otherSessions={sessions.filter((_, i) => i !== activeSessionIdx)}
            />
          </div>

          <div className={activeTab === "coach" ? "" : "hidden"}>
            <div className="space-y-6">
              {corner_suggestions && (
                <CornerSuggestions data={corner_suggestions} />
              )}
              <CoachingPanel token={analysis.token} />
            </div>
          </div>
        </div>

        {/* Right: persistent track map sidebar (desktop only) */}
        <div className="hidden lg:block w-80 xl:w-96 flex-shrink-0 sticky top-4 self-start">
          {trackMapSidebar}
        </div>
      </div>

      {/* Chat FAB */}
      <ChatPanel token={analysis.token} />
    </div>
  );
}
