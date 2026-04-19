"use client";

import { useState } from "react";
import { TheoreticalBest, LapSummary, formatLapTime } from "@/lib/api";

interface TheoreticalBestBreakdownProps {
  theoretical: TheoreticalBest;
  laps: LapSummary[];
}

export default function TheoreticalBestBreakdown({
  theoretical,
  laps,
}: TheoreticalBestBreakdownProps) {
  const [expanded, setExpanded] = useState(true);

  if (!theoretical.segment_sources || theoretical.segment_sources.length === 0) {
    return null;
  }

  const segments = theoretical.segment_sources;
  const bestLapNum = theoretical.best_lap_number;
  const validLaps = laps
    .filter((l) => l.delta_to_best_s < 25)
    .sort((a, b) => a.lap_time_s - b.lap_time_s);

  // Compute per-segment delta (how much the best lap lost vs theoretical best in each sector)
  const segmentDeltas = segments.map((seg) => {
    const bestLapTime = seg.per_lap_times?.[bestLapNum];
    return bestLapTime != null ? bestLapTime - seg.best_time_s : 0;
  });
  const maxDelta = Math.max(...segmentDeltas, 0.001);

  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700/30 overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-left touch-manipulation hover:bg-gray-800/80 transition-colors"
      >
        <div>
          <h3 className="text-sm font-semibold text-white">
            Theoretical Best Breakdown
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Best of each sector combined across {new Set(segments.map((s) => s.from_lap)).size} laps
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-lg font-mono font-bold text-blue-400">
              {formatLapTime(theoretical.theoretical_best_time_s)}
            </div>
            <div className="text-[10px] text-yellow-400 font-mono">
              -{theoretical.time_delta_s.toFixed(3)}s vs best
            </div>
          </div>
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-700/30">
          {/* Sector cards */}
          <div className="p-3 space-y-1.5">
            {segments.map((seg, i) => {
              const bestLapTime = seg.per_lap_times?.[bestLapNum];
              const delta = segmentDeltas[i];
              const isFromBestLap = seg.from_lap === bestLapNum;
              const intensity = delta / maxDelta;
              const isBigGain = delta > maxDelta * 0.5;

              return (
                <div
                  key={i}
                  className="relative rounded-lg overflow-hidden"
                >
                  {/* Gain bar background */}
                  {delta > 0.001 && (
                    <div
                      className={`absolute inset-y-0 left-0 ${
                        isBigGain
                          ? "bg-gradient-to-r from-yellow-500/20 to-transparent"
                          : "bg-gradient-to-r from-yellow-500/10 to-transparent"
                      }`}
                      style={{ width: `${Math.max(intensity * 100, 5)}%` }}
                    />
                  )}

                  <div className="relative flex items-center gap-3 px-3 py-2.5">
                    {/* Sector number */}
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                        isBigGain
                          ? "bg-yellow-500/30 text-yellow-300 ring-1 ring-yellow-500/40"
                          : isFromBestLap
                          ? "bg-green-500/20 text-green-400"
                          : "bg-blue-500/20 text-blue-400"
                      }`}
                    >
                      {i + 1}
                    </div>

                    {/* Label + details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-200 truncate">
                          {seg.label}
                        </span>
                        {isBigGain && (
                          <span className="text-[9px] font-bold uppercase tracking-wider text-yellow-400 bg-yellow-500/15 px-1.5 py-0.5 rounded">
                            Key Gain
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-[11px]">
                        <span className="text-gray-500">
                          Best: <span className="font-mono text-white">{seg.best_time_s.toFixed(3)}s</span>
                        </span>
                        <span className="text-gray-500">
                          from{" "}
                          <span
                            className={`font-mono ${
                              isFromBestLap ? "text-green-400" : "text-blue-400"
                            }`}
                          >
                            Lap {seg.from_lap}
                          </span>
                        </span>
                      </div>
                    </div>

                    {/* Delta vs best lap */}
                    <div className="text-right flex-shrink-0">
                      {delta > 0.001 ? (
                        <div className="text-sm font-mono font-bold text-yellow-400">
                          +{delta.toFixed(3)}s
                        </div>
                      ) : (
                        <div className="text-sm font-mono text-green-400">
                          Best
                        </div>
                      )}
                      {bestLapTime != null && delta > 0.001 && (
                        <div className="text-[10px] text-gray-500 font-mono">
                          L{bestLapNum}: {bestLapTime.toFixed(3)}s
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Per-lap sector comparison table */}
          {validLaps.length > 1 && segments[0]?.per_lap_times && (
            <div className="border-t border-gray-700/40 px-4 py-3">
              <div className="text-[10px] text-gray-500 font-semibold uppercase tracking-wide mb-2">
                Sector Comparison Across Laps
              </div>
              <div className="overflow-x-auto -mx-1">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500">
                      <th className="text-left py-1.5 pr-2 font-medium sticky left-0 bg-gray-800/50">Sector</th>
                      {validLaps.slice(0, 8).map((l) => (
                        <th
                          key={l.lap_number}
                          className={`text-center py-1.5 px-2 font-mono font-medium min-w-[52px] ${
                            l.lap_number === bestLapNum ? "text-green-400" : ""
                          }`}
                        >
                          L{l.lap_number}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700/20">
                    {segments.map((seg, i) => {
                      const sectorBest = seg.best_time_s;
                      return (
                        <tr key={i}>
                          <td className="py-1.5 pr-2 text-gray-400 whitespace-nowrap sticky left-0 bg-gray-800/50">
                            <span className="inline-flex items-center gap-1.5">
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  segmentDeltas[i] > maxDelta * 0.5
                                    ? "bg-yellow-400"
                                    : "bg-gray-600"
                                }`}
                              />
                              {seg.label}
                            </span>
                          </td>
                          {validLaps.slice(0, 8).map((l) => {
                            const t = seg.per_lap_times?.[l.lap_number];
                            const isBest = t != null && Math.abs(t - sectorBest) < 0.001;
                            return (
                              <td
                                key={l.lap_number}
                                className={`text-center py-1.5 px-2 font-mono ${
                                  isBest
                                    ? "text-blue-400 font-bold"
                                    : t != null
                                    ? "text-gray-300"
                                    : "text-gray-700"
                                }`}
                              >
                                {t != null ? t.toFixed(2) : "-"}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
