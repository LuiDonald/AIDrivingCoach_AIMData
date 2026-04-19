"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { listSessions, deleteSession, SessionResponse, formatLapTime } from "@/lib/api";
import FileUpload from "@/components/FileUpload";

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchSessions = useCallback(() => {
    listSessions()
      .then(setSessions)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Delete this session? This cannot be undone.")) return;
    setDeleting(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err) {
      console.error("Failed to delete session:", err);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-white">Sessions</h1>
      </div>

      <div className="mb-6">
        <FileUpload compact onUploadComplete={fetchSessions} />
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
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-white">
                  {s.track_name || s.filename}
                </div>
                <div className="text-sm text-gray-400 mt-0.5">
                  {s.num_laps} laps
                  {s.session_date && ` · ${new Date(s.session_date).toLocaleDateString()}`}
                  {s.device_model && ` · ${s.device_model}`}
                </div>
              </div>
              <div className="flex items-center gap-3 ml-3">
                <div className="text-right">
                  {s.best_lap_time_s && (
                    <div className="text-green-400 font-mono font-bold">
                      {formatLapTime(s.best_lap_time_s)}
                    </div>
                  )}
                  <div className="text-xs text-gray-500">best lap</div>
                </div>
                <button
                  onClick={(e) => handleDelete(e, s.id)}
                  disabled={deleting === s.id}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors touch-manipulation disabled:opacity-50"
                  title="Delete session"
                >
                  {deleting === s.id ? (
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
