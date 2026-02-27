"use client";

import { useEffect, useState } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { getGGDiagram, GGData } from "@/lib/api";

interface Props {
  sessionId: string;
  lapNumber: number | null;
}

export default function GGDiagram({ sessionId, lapNumber }: Props) {
  const [data, setData] = useState<GGData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!lapNumber) return;
    setLoading(true);
    getGGDiagram(sessionId, lapNumber)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId, lapNumber]);

  if (!lapNumber) {
    return (
      <div className="text-gray-500 text-center py-8 text-sm">
        Select a lap to view the G-G diagram
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

  if (!data || data.lateral_g.length === 0) return null;

  const points = data.lateral_g.map((lat, i) => ({
    lateral: Math.round(lat * 100) / 100,
    longitudinal: Math.round(data.longitudinal_g[i] * 100) / 100,
  }));

  const sampled = points.length > 1000
    ? points.filter((_, i) => i % Math.ceil(points.length / 1000) === 0)
    : points;

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
        G-G Diagram <span className="text-gray-500 font-normal">Lap {lapNumber}</span>
      </h3>
      <div className="bg-gray-800/50 rounded-xl p-2 md:p-4">
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              type="number"
              dataKey="lateral"
              name="Lateral G"
              stroke="#6B7280"
              fontSize={11}
              domain={["auto", "auto"]}
              label={{ value: "Lateral G", position: "bottom", fill: "#6B7280", fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="longitudinal"
              name="Longitudinal G"
              stroke="#6B7280"
              fontSize={11}
              domain={["auto", "auto"]}
              label={{ value: "Long. G", angle: -90, position: "insideLeft", fill: "#6B7280", fontSize: 11 }}
            />
            <ReferenceLine x={0} stroke="#4B5563" />
            <ReferenceLine y={0} stroke="#4B5563" />
            <Tooltip
              contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
              formatter={(value) => [`${value}g`]}
            />
            <Scatter data={sampled} fill="#3B82F6" fillOpacity={0.4} r={2} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
