"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getSession,
  getLaps,
  getTheoreticalBest,
  getConsistency,
  SessionResponse,
  LapSummary,
  TheoreticalBest,
  ConsistencyReport,
  formatLapTime,
} from "@/lib/api";
import LapTable from "@/components/LapTable";
import SpeedTraceChart from "@/components/SpeedTraceChart";
import GGDiagram from "@/components/GGDiagram";
import TrackMap from "@/components/TrackMap";
import CornerSuggestions from "@/components/CornerSuggestions";
import LapComparison from "@/components/LapComparison";
import CoachingPanel from "@/components/CoachingPanel";
import ChatPanel from "@/components/ChatPanel";
import PhotoUpload from "@/components/PhotoUpload";

type Tab = "overview" | "compare" | "analysis" | "coach" | "photos";

export default function SessionPage() {
  const params = useParams();
  const sessionId = params.id as string;

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [laps, setLaps] = useState<LapSummary[]>([]);
  const [selectedLaps, setSelectedLaps] = useState<number[]>([]);
  const [theoretical, setTheoretical] = useState<TheoreticalBest | null>(null);
  const [consistency, setConsistency] = useState<ConsistencyReport | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [mapCollapsed, setMapCollapsed] = useState(false);

  useEffect(() => {
    Promise.all([
      getSession(sessionId),
      getLaps(sessionId),
      getTheoreticalBest(sessionId).catch(() => null),
      getConsistency(sessionId).catch(() => null),
    ])
      .then(([s, l, t, c]) => {
        setSession(s);
        setLaps(l);
        setTheoretical(t);
        setConsistency(c);
        if (s.best_lap_number) {
          setSelectedLaps([s.best_lap_number]);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId]);

  const toggleLap = (lap: number) => {
    setSelectedLaps((prev) =>
      prev.includes(lap) ? prev.filter((l) => l !== lap) : [...prev, lap],
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-gray-400">
        <svg className="animate-spin w-8 h-8 mr-3 text-blue-500" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading session...
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen text-gray-400">
        <p>Session not found</p>
        <Link href="/sessions" className="text-blue-400 mt-2">Back to sessions</Link>
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "compare", label: "Compare" },
    { key: "analysis", label: "Analysis" },
    { key: "coach", label: "AI Coach" },
    { key: "photos", label: "Photos" },
  ];

  const activeLap = selectedLaps.length > 0 ? selectedLaps[0] : (session.best_lap_number || null);

  const trackMapSidebar = (
    <div className="space-y-3">
      <TrackMap
        sessionId={sessionId}
        lapNumber={activeLap}
      />
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <Link href="/sessions" className="text-xs text-gray-500 hover:text-gray-300 mb-1 block">
            &larr; Sessions
          </Link>
          <h1 className="text-xl md:text-2xl font-bold text-white">
            {session.track_name || session.filename}
          </h1>
          <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-400">
            {session.session_date && (
              <span>{new Date(session.session_date).toLocaleDateString()}</span>
            )}
            <span>{session.num_laps} laps</span>
            {session.device_model && <span>{session.device_model}</span>}
          </div>
        </div>
        {session.best_lap_time_s && (
          <div className="text-right flex-shrink-0">
            <div className="text-2xl font-mono font-bold text-green-400">
              {formatLapTime(session.best_lap_time_s)}
            </div>
            <div className="text-xs text-gray-500">best lap</div>
          </div>
        )}
      </div>

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
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {!mapCollapsed && <div className="mt-2">{trackMapSidebar}</div>}
      </div>

      {/* Two-column layout: content left, track map right */}
      <div className="flex gap-4">
        {/* Left: main content area */}
        <div className="flex-1 min-w-0">
          {/* Tab bar */}
          <div className="flex gap-1 bg-gray-800/30 rounded-xl p-1 mb-4 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
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

          {/* Tab content */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              <LapTable laps={laps} selectedLaps={selectedLaps} onToggleLap={toggleLap} />
              <SpeedTraceChart sessionId={sessionId} lapNumbers={selectedLaps} />
            </div>
          )}

          {activeTab === "compare" && (
            <LapComparison
              sessionId={sessionId}
              laps={laps}
              selectedLaps={selectedLaps}
              onSelectLaps={setSelectedLaps}
            />
          )}

          {activeTab === "analysis" && (
            <div className="space-y-6">
              <SpeedTraceChart sessionId={sessionId} lapNumbers={selectedLaps} />
              <GGDiagram
                sessionId={sessionId}
                lapNumber={activeLap}
              />
              <CornerSuggestions sessionId={sessionId} />
              <LapTable laps={laps} selectedLaps={selectedLaps} onToggleLap={toggleLap} />
            </div>
          )}

          {activeTab === "coach" && (
            <div className="space-y-6">
              <CornerSuggestions sessionId={sessionId} />
              <CoachingPanel sessionId={sessionId} />
            </div>
          )}

          {activeTab === "photos" && (
            <PhotoUpload sessionId={sessionId} />
          )}
        </div>

        {/* Right: persistent track map sidebar (desktop only) */}
        <div className="hidden lg:block w-80 xl:w-96 flex-shrink-0 sticky top-4 self-start">
          {trackMapSidebar}
        </div>
      </div>

      {/* Chat FAB */}
      <ChatPanel sessionId={sessionId} />
    </div>
  );
}
