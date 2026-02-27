"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listSessions, SessionResponse, formatLapTime } from "@/lib/api";

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Sessions</h1>
        <Link
          href="/"
          className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors touch-manipulation"
        >
          Upload New
        </Link>
      </div>

      {loading && (
        <div className="text-center py-12 text-gray-400">Loading sessions...</div>
      )}

      {!loading && sessions.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-400 mb-4">No sessions yet</p>
          <Link
            href="/"
            className="text-blue-400 hover:text-blue-300 text-sm"
          >
            Upload your first telemetry file
          </Link>
        </div>
      )}

      <div className="space-y-3">
        {sessions.map((s) => (
          <Link
            key={s.id}
            href={`/sessions/${s.id}`}
            className="block bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 rounded-xl p-4 transition-colors active:scale-[0.99] touch-manipulation"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-white">
                  {s.track_name || s.filename}
                </div>
                <div className="text-sm text-gray-400 mt-0.5">
                  {s.num_laps} laps
                  {s.session_date && ` · ${new Date(s.session_date).toLocaleDateString()}`}
                  {s.device_model && ` · ${s.device_model}`}
                </div>
              </div>
              <div className="text-right">
                {s.best_lap_time_s && (
                  <div className="text-green-400 font-mono font-bold">
                    {formatLapTime(s.best_lap_time_s)}
                  </div>
                )}
                <div className="text-xs text-gray-500">best lap</div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
