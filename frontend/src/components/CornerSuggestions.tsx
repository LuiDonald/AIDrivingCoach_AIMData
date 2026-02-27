"use client";

import { useEffect, useState } from "react";
import { getCornerSuggestions, CornerSuggestionsResponse, CornerSuggestion } from "@/lib/api";

interface CornerSuggestionsProps {
  sessionId: string;
}

const CATEGORY_ICONS: Record<string, string> = {
  braking: "🟥",
  entry_speed: "🟧",
  apex_speed: "🟨",
  exit_speed: "🟩",
  throttle: "🟦",
  flat_out: "⚡",
};

const CATEGORY_LABELS: Record<string, string> = {
  braking: "Braking Point",
  entry_speed: "Entry Speed",
  apex_speed: "Apex Speed",
  exit_speed: "Exit Speed",
  throttle: "Throttle Application",
  flat_out: "Stay Flat",
};

function PriorityBadge({ priority }: { priority: string }) {
  const colors = {
    HIGH: "bg-red-500/20 text-red-400 border-red-500/30",
    MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    LOW: "bg-green-500/20 text-green-400 border-green-500/30",
  };
  return (
    <span
      className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${colors[priority as keyof typeof colors] || colors.MEDIUM}`}
    >
      {priority}
    </span>
  );
}

function SuggestionCard({ suggestion }: { suggestion: CornerSuggestion }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <button
      onClick={() => setExpanded(!expanded)}
      className="w-full text-left bg-gray-800/60 rounded-lg p-3 border border-gray-700/40 hover:border-gray-600/60 transition-colors touch-manipulation"
    >
          <div className="flex items-start gap-2">
        <span className="text-lg leading-none mt-0.5">
          {CATEGORY_ICONS[suggestion.category] || "🔵"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-gray-300">
              {suggestion.corner_label || `Turn ${suggestion.corner_id}`} · {CATEGORY_LABELS[suggestion.category] || suggestion.category}
            </span>
            <PriorityBadge priority={suggestion.priority} />
            {suggestion.estimated_gain_s && suggestion.estimated_gain_s > 0 && (
              <span className="text-[10px] font-mono text-green-400 ml-auto flex-shrink-0">
                ~{suggestion.estimated_gain_s.toFixed(2)}s
              </span>
            )}
          </div>
          <p className="text-sm text-gray-200 leading-snug">{suggestion.suggestion}</p>

          {expanded && suggestion.data && (
            <div className="mt-2 pt-2 border-t border-gray-700/40 grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(suggestion.data).map(([key, value]) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-gray-500">{key.replace(/_/g, " ")}</span>
                  <span className="text-gray-300 font-mono">
                    {typeof value === "number" ? value.toFixed(1) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

export default function CornerSuggestions({ sessionId }: CornerSuggestionsProps) {
  const [data, setData] = useState<CornerSuggestionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCornerSuggestions(sessionId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700/30 flex items-center justify-center text-gray-400">
        <svg className="animate-spin w-5 h-5 mr-2 text-blue-500" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Analyzing corners...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700/30 text-center text-red-400 text-sm">
        {error}
      </div>
    );
  }

  if (!data) return null;

  const categories = ["all", ...new Set(data.suggestions.map((s) => s.category))];
  const filtered = filter === "all" ? data.suggestions : data.suggestions.filter((s) => s.category === filter);

  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700/30 overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-white">Where Can You Improve?</h3>
          {data.total_estimated_gain_s > 0 && (
            <span className="text-xs font-mono text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full border border-green-500/20">
              ~{data.total_estimated_gain_s.toFixed(2)}s potential
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500 mb-3">{data.summary}</p>

        {/* Category filters */}
        <div className="flex gap-1 overflow-x-auto pb-1">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className={`text-[11px] px-2 py-1 rounded-full whitespace-nowrap transition-colors touch-manipulation ${
                filter === cat
                  ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                  : "bg-gray-700/30 text-gray-400 border border-transparent hover:text-gray-300"
              }`}
            >
              {cat === "all"
                ? `All (${data.suggestions.length})`
                : `${CATEGORY_ICONS[cat] || ""} ${CATEGORY_LABELS[cat] || cat}`}
            </button>
          ))}
        </div>
      </div>

      {/* Suggestions list */}
      <div className="px-4 pb-4 space-y-2 max-h-[500px] overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="text-center text-gray-500 text-sm py-4">
            No suggestions found. Your driving is very consistent!
          </p>
        ) : (
          filtered.map((s, i) => <SuggestionCard key={`${s.corner_id}-${s.category}-${i}`} suggestion={s} />)
        )}
      </div>
    </div>
  );
}
