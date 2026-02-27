"use client";

import { LapSummary, formatLapTime, formatDelta, kphToMph } from "@/lib/api";

interface LapTableProps {
  laps: LapSummary[];
  selectedLaps: number[];
  onToggleLap: (lap: number) => void;
}

export default function LapTable({ laps, selectedLaps, onToggleLap }: LapTableProps) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider px-1">
        Lap Times
      </h3>
      <div className="space-y-1.5">
        {laps.map((lap) => {
          const isBest = lap.delta_to_best_s === 0;
          const isSelected = selectedLaps.includes(lap.lap_number);
          return (
            <button
              key={lap.lap_number}
              onClick={() => onToggleLap(lap.lap_number)}
              className={`w-full flex items-center justify-between p-3 rounded-xl transition-all active:scale-[0.98] touch-manipulation ${
                isSelected
                  ? "bg-blue-600/20 border border-blue-500/40"
                  : "bg-gray-800/50 border border-transparent hover:bg-gray-800"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    isBest
                      ? "bg-green-500/20 text-green-400"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  {lap.lap_number}
                </div>
                <div className="text-left">
                  <div className={`font-mono text-base ${isBest ? "text-green-400 font-bold" : "text-white"}`}>
                    {formatLapTime(lap.lap_time_s)}
                  </div>
                  {lap.max_speed_kph && (
                    <div className="text-xs text-gray-500">
                      {Math.round(kphToMph(lap.max_speed_kph))} mph max
                    </div>
                  )}
                </div>
              </div>
              <div className="text-right">
                <div className={`text-sm font-mono ${
                  isBest ? "text-green-400" : lap.delta_to_best_s < 1 ? "text-yellow-400" : "text-red-400"
                }`}>
                  {isBest ? "BEST" : formatDelta(lap.delta_to_best_s)}
                </div>
                {lap.max_lateral_g && (
                  <div className="text-xs text-gray-500">
                    {lap.max_lateral_g.toFixed(2)}g lat
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
