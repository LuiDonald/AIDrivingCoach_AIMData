"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { uploadSession } from "@/lib/api";

export default function FileUpload() {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>("");

  const handleFile = useCallback(
    async (file: File) => {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (!ext || !["xrk", "xrz", "csv"].includes(ext)) {
        setError("Unsupported file type. Please upload .xrk, .xrz, or .csv files.");
        return;
      }

      setIsUploading(true);
      setError(null);
      setProgress("Uploading and parsing telemetry data...");

      try {
        const session = await uploadSession(file);
        setProgress("Done! Redirecting...");
        router.push(`/sessions/${session.id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
        setIsUploading(false);
        setProgress("");
      }
    },
    [router],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  return (
    <div className="w-full max-w-lg mx-auto">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-2xl p-8 md:p-12 text-center transition-all ${
          isDragging
            ? "border-blue-500 bg-blue-500/10"
            : "border-gray-600 hover:border-gray-400"
        } ${isUploading ? "opacity-60 pointer-events-none" : ""}`}
      >
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-blue-500/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>

          <div>
            <p className="text-lg font-semibold text-white">
              {isUploading ? progress : "Upload Telemetry File"}
            </p>
            <p className="text-sm text-gray-400 mt-1">
              AIM SOLO / SOLO DL files (.xrk, .xrz, .csv)
            </p>
          </div>

          {!isUploading && (
            <label className="cursor-pointer bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-8 rounded-xl text-base transition-colors active:scale-95 touch-manipulation">
              <input
                type="file"
                accept=".xrk,.xrz,.csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                }}
              />
              Choose File
            </label>
          )}

          {isUploading && (
            <div className="flex items-center gap-2 text-blue-400">
              <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm">Processing...</span>
            </div>
          )}

          <p className="text-xs text-gray-500 hidden md:block">
            or drag and drop your file here
          </p>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
