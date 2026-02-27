"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { getSpeedTraces, SpeedTrace, kphToMph } from "@/lib/api";

const LAP_COLORS = [
  "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#06B6D4", "#F97316",
];

interface Props {
  sessionId: string;
  lapNumbers: number[];
}

export default function SpeedTraceChart({ sessionId, lapNumbers }: Props) {
  const [traces, setTraces] = useState<Record<string, SpeedTrace>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (lapNumbers.length === 0) return;
    setLoading(true);
    getSpeedTraces(sessionId, lapNumbers)
      .then(setTraces)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId, lapNumbers]);

  if (lapNumbers.length === 0) {
    return (
      <div className="text-gray-500 text-center py-8">
        Select laps above to compare speed traces
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-400">
        <svg className="animate-spin w-5 h-5 mr-2" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading...
      </div>
    );
  }

  const keys = Object.keys(traces);
  if (keys.length === 0) return null;

  const refKey = keys[0];
  const refTrace = traces[refKey];
  const chartData = refTrace.distance_m.map((d, i) => {
    const point: Record<string, number> = { distance: Math.round(d) };
    for (const key of keys) {
      const t = traces[key];
      if (i < t.speed_kph.length) {
        point[`lap_${key}`] = Math.round(kphToMph(t.speed_kph[i]) * 10) / 10;
      }
    }
    return point;
  });

  const sampled = chartData.length > 500
    ? chartData.filter((_, i) => i % Math.ceil(chartData.length / 500) === 0)
    : chartData;

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
        Speed Trace
      </h3>
      <div className="bg-gray-800/50 rounded-xl p-2 md:p-4">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={sampled}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="distance"
              stroke="#6B7280"
              fontSize={11}
              tickFormatter={(v) => `${v}m`}
            />
            <YAxis
              stroke="#6B7280"
              fontSize={11}
              tickFormatter={(v) => `${v}`}
              label={{ value: "mph", angle: -90, position: "insideLeft", fill: "#6B7280", fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
              labelFormatter={(v) => `${v}m`}
              formatter={(value, name) => [`${value} mph`, `Lap ${String(name).replace("lap_", "")}`]}
            />
            <Legend formatter={(value) => `Lap ${value.replace("lap_", "")}`} />
            {keys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={`lap_${key}`}
                stroke={LAP_COLORS[i % LAP_COLORS.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
