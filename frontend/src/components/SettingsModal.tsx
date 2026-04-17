"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getStoredApiKey,
  setStoredApiKey,
  validateApiKey,
} from "@/lib/api";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [validating, setValidating] = useState(false);
  const [status, setStatus] = useState<{
    type: "success" | "error" | "idle";
    message: string;
  }>({ type: "idle", message: "" });

  useEffect(() => {
    if (open) {
      const stored = getStoredApiKey();
      setApiKey(stored);
      setSaved(!!stored);
      setStatus(
        stored
          ? { type: "success", message: "Key saved locally" }
          : { type: "idle", message: "" },
      );
    }
  }, [open]);

  const handleSave = useCallback(async () => {
    const trimmed = apiKey.trim();
    if (!trimmed) {
      setStoredApiKey("");
      setSaved(false);
      setStatus({ type: "idle", message: "Key cleared" });
      return;
    }

    setValidating(true);
    setStatus({ type: "idle", message: "Validating..." });

    try {
      const result = await validateApiKey(trimmed);
      if (result.valid) {
        setStoredApiKey(trimmed);
        setSaved(true);
        setStatus({ type: "success", message: "Valid key saved" });
      } else {
        setStatus({
          type: "error",
          message: result.error || "Invalid API key",
        });
      }
    } catch {
      setStatus({ type: "error", message: "Could not reach server to validate" });
    } finally {
      setValidating(false);
    }
  }, [apiKey]);

  const handleClear = useCallback(() => {
    setApiKey("");
    setStoredApiKey("");
    setSaved(false);
    setStatus({ type: "idle", message: "Key removed" });
  }, []);

  if (!open) return null;

  const masked = saved && apiKey ? `sk-...${apiKey.slice(-4)}` : "";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Settings
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              OpenAI API Key
            </label>
            <p className="text-xs text-gray-500 mb-3">
              Your key is stored only in this browser&apos;s local storage and
              sent directly to OpenAI. It is never saved on the server.
            </p>

            {saved && !validating ? (
              <div className="flex items-center gap-3">
                <div className="flex-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-sm text-gray-400 font-mono">
                  {masked}
                </div>
                <button
                  onClick={() => setSaved(false)}
                  className="px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  Change
                </button>
                <button
                  onClick={handleClear}
                  className="px-3 py-2 text-sm bg-red-900/50 hover:bg-red-800/60 text-red-300 rounded-lg transition-colors"
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setStatus({ type: "idle", message: "" });
                  }}
                  onKeyDown={(e) => e.key === "Enter" && handleSave()}
                  placeholder="sk-..."
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
                  autoFocus
                />
                <button
                  onClick={handleSave}
                  disabled={validating || !apiKey.trim()}
                  className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  {validating ? "Validating..." : "Save & Validate"}
                </button>
              </div>
            )}
          </div>

          {status.message && (
            <p
              className={`text-xs font-medium ${
                status.type === "success"
                  ? "text-green-400"
                  : status.type === "error"
                    ? "text-red-400"
                    : "text-gray-400"
              }`}
            >
              {status.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
