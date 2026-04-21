"use client";

import { useState, useEffect } from "react";
import { generateCoachingReport, CoachingReport } from "@/lib/api";

interface Props {
  token: string;
  cachedReport?: CoachingReport | null;
}

const PRIORITY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  HIGH: { bg: "bg-red-500/10 border-red-500/30", text: "text-red-400", dot: "bg-red-500" },
  MEDIUM: { bg: "bg-yellow-500/10 border-yellow-500/30", text: "text-yellow-400", dot: "bg-yellow-500" },
  LOW: { bg: "bg-blue-500/10 border-blue-500/30", text: "text-blue-400", dot: "bg-blue-500" },
};

const CATEGORY_ICONS: Record<string, string> = {
  braking: "B",
  throttle: "T",
  line: "L",
  consistency: "C",
  setup: "S",
  general: "G",
};

export default function CoachingPanel({ token, cachedReport }: Props) {
  const [report, setReport] = useState<CoachingReport | null>(cachedReport || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await generateCoachingReport(token);
      setReport(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate report");
    } finally {
      setLoading(false);
    }
  };

  if (!report && !loading) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-400 mb-4">Get AI-powered coaching recommendations</p>
        <button
          onClick={generate}
          className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 px-8 rounded-xl transition-all active:scale-95 touch-manipulation"
        >
          Generate Coaching Report
        </button>
        {error && (
          <p className="text-red-400 text-sm mt-3">{error}</p>
        )}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-400">
        <svg className="animate-spin w-8 h-8 mb-3 text-blue-500" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <p className="text-sm">Analyzing your driving data...</p>
        <p className="text-xs text-gray-500 mt-1">This may take 10-20 seconds</p>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="space-y-4">
      <div className="bg-gradient-to-r from-blue-600/10 to-purple-600/10 border border-blue-500/20 rounded-xl p-4">
        <p className="text-white text-sm leading-relaxed">{report.summary}</p>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Recommendations
        </h4>
        {report.recommendations.map((rec, i) => {
          const style = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.LOW;
          return (
            <div key={i} className={`border rounded-xl p-3 ${style.bg}`}>
              <div className="flex items-start gap-3">
                <div className="flex flex-col items-center gap-1 flex-shrink-0">
                  <div className={`w-2 h-2 rounded-full ${style.dot}`} />
                  <span className="text-[10px] text-gray-500 font-semibold">
                    {CATEGORY_ICONS[rec.category] || "?"}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-bold ${style.text}`}>{rec.priority}</span>
                    {rec.corner_id && (
                      <span className="text-xs text-gray-500">Corner {rec.corner_id}</span>
                    )}
                    {rec.estimated_gain_s && (
                      <span className="text-xs text-green-400 ml-auto font-mono">
                        ~{rec.estimated_gain_s.toFixed(1)}s
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-200 leading-relaxed">{rec.description}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
        <p className="text-gray-300 text-sm italic">{report.overall_assessment}</p>
      </div>
    </div>
  );
}
