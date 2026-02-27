"use client";

import { useState } from "react";
import { uploadPhoto } from "@/lib/api";

interface Props {
  sessionId: string;
}

const TIRE_POSITIONS = [
  { type: "tire_fl", label: "Front Left" },
  { type: "tire_fr", label: "Front Right" },
  { type: "tire_rl", label: "Rear Left" },
  { type: "tire_rr", label: "Rear Right" },
];

const CAR_ANGLES = [
  { type: "car_front", label: "Front" },
  { type: "car_side", label: "Side" },
  { type: "car_rear", label: "Rear" },
  { type: "car_34", label: "3/4 View" },
];

interface PhotoResult {
  type: string;
  analysis: Record<string, unknown>;
}

export default function PhotoUpload({ sessionId }: Props) {
  const [results, setResults] = useState<Record<string, PhotoResult>>({});
  const [uploading, setUploading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"tires" | "car">("tires");

  const handleUpload = async (photoType: string, file: File) => {
    setUploading(photoType);
    try {
      const result = await uploadPhoto(sessionId, photoType, file);
      setResults((prev) => ({
        ...prev,
        [photoType]: { type: photoType, analysis: result.analysis },
      }));
    } catch (e) {
      console.error("Photo upload failed:", e);
    } finally {
      setUploading(null);
    }
  };

  const renderPhotoSlot = (type: string, label: string) => {
    const result = results[type];
    const isUploading = uploading === type;

    return (
      <div key={type} className="bg-gray-800/50 rounded-xl border border-gray-700/50 overflow-hidden">
        <label className="block cursor-pointer">
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(type, file);
            }}
            disabled={isUploading}
          />
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">{label}</span>
              {isUploading && (
                <svg className="animate-spin w-4 h-4 text-blue-400" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {result && !isUploading && (
                <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>

            {!result && !isUploading && (
              <div className="flex items-center justify-center h-20 border-2 border-dashed border-gray-600 rounded-lg">
                <div className="text-center">
                  <svg className="w-6 h-6 text-gray-500 mx-auto mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="text-xs text-gray-500">Tap to capture</span>
                </div>
              </div>
            )}

            {isUploading && (
              <div className="flex items-center justify-center h-20 text-gray-400 text-sm">
                Analyzing...
              </div>
            )}

            {result && !isUploading && (
              <div className="space-y-1 text-xs">
                {type.startsWith("tire_") && (
                  <>
                    {result.analysis.compound && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Compound</span>
                        <span className="text-white">{String(result.analysis.compound)}</span>
                      </div>
                    )}
                    {result.analysis.wear_pattern && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Wear</span>
                        <span className="text-white">{String(result.analysis.wear_pattern).replace("_", " ")}</span>
                      </div>
                    )}
                    {result.analysis.wear_severity_pct != null && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Life</span>
                        <span className={`font-mono ${
                          Number(result.analysis.wear_severity_pct) > 50
                            ? "text-green-400"
                            : Number(result.analysis.wear_severity_pct) > 20
                            ? "text-yellow-400"
                            : "text-red-400"
                        }`}>
                          {String(result.analysis.wear_severity_pct)}%
                        </span>
                      </div>
                    )}
                    {result.analysis.condition_summary && (
                      <p className="text-gray-400 mt-1 leading-relaxed">
                        {String(result.analysis.condition_summary)}
                      </p>
                    )}
                  </>
                )}
                {type.startsWith("car_") && (
                  <>
                    {result.analysis.aero_level && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Aero</span>
                        <span className={`font-semibold ${
                          result.analysis.aero_level === "full"
                            ? "text-green-400"
                            : result.analysis.aero_level === "mild"
                            ? "text-yellow-400"
                            : "text-gray-400"
                        }`}>
                          {String(result.analysis.aero_level)}
                        </span>
                      </div>
                    )}
                    {result.analysis.vehicle_type && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Type</span>
                        <span className="text-white">{String(result.analysis.vehicle_type)}</span>
                      </div>
                    )}
                    {Array.isArray(result.analysis.aero_components) && result.analysis.aero_components.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(result.analysis.aero_components as string[]).map((c) => (
                          <span key={c} className="bg-blue-500/20 text-blue-400 text-[10px] px-1.5 py-0.5 rounded">
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </label>
      </div>
    );
  };

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <button
          onClick={() => setActiveTab("tires")}
          className={`text-sm font-medium px-4 py-2 rounded-lg transition-colors touch-manipulation ${
            activeTab === "tires"
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:text-white"
          }`}
        >
          Tires
        </button>
        <button
          onClick={() => setActiveTab("car")}
          className={`text-sm font-medium px-4 py-2 rounded-lg transition-colors touch-manipulation ${
            activeTab === "car"
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:text-white"
          }`}
        >
          Car Setup
        </button>
      </div>

      {activeTab === "tires" && (
        <div className="grid grid-cols-2 gap-2">
          {TIRE_POSITIONS.map((t) => renderPhotoSlot(t.type, t.label))}
        </div>
      )}

      {activeTab === "car" && (
        <div className="grid grid-cols-2 gap-2">
          {CAR_ANGLES.map((c) => renderPhotoSlot(c.type, c.label))}
        </div>
      )}
    </div>
  );
}
