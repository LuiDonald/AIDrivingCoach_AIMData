"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { uploadSession, DuplicateSessionError } from "@/lib/api";

interface FileUploadProps {
  compact?: boolean;
  onUploadComplete?: () => void;
}

const SUPPORTED_EXTENSIONS = ["xrk", "xrz", "csv"];

function getFileExtension(filename: string): string | undefined {
  return filename.split(".").pop()?.toLowerCase();
}

function validateFiles(files: File[]): { valid: File[]; invalid: string[] } {
  const valid: File[] = [];
  const invalid: string[] = [];
  for (const file of files) {
    const ext = getFileExtension(file.name);
    if (ext && SUPPORTED_EXTENSIONS.includes(ext)) {
      valid.push(file);
    } else {
      invalid.push(file.name);
    }
  }
  return { valid, invalid };
}

export default function FileUpload({ compact, onUploadComplete }: FileUploadProps) {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>("");
  const [uploadResults, setUploadResults] = useState<{ succeeded: number; failed: string[] } | null>(null);

  const handleFiles = useCallback(
    async (files: File[]) => {
      const { valid, invalid } = validateFiles(files);

      if (valid.length === 0) {
        setError(
          invalid.length > 0
            ? `Unsupported file type${invalid.length > 1 ? "s" : ""}: ${invalid.join(", ")}. Use .xrk, .xrz, or .csv files.`
            : "No files selected."
        );
        return;
      }

      setIsUploading(true);
      setError(null);
      setUploadResults(null);

      const failed: string[] = [];
      const duplicates: string[] = [];
      let lastSessionId: string | null = null;

      for (let i = 0; i < valid.length; i++) {
        const file = valid[i];
        const label = valid.length === 1
          ? "Uploading and parsing telemetry data..."
          : `Uploading file ${i + 1} of ${valid.length}: ${file.name}`;
        setProgress(label);

        try {
          const session = await uploadSession(file);
          lastSessionId = session.id;
        } catch (e) {
          if (e instanceof DuplicateSessionError) {
            duplicates.push(file.name);
          } else {
            failed.push(`${file.name}: ${e instanceof Error ? e.message : "upload failed"}`);
          }
        }
      }

      const succeeded = valid.length - failed.length - duplicates.length;

      const warnings: string[] = [];
      if (invalid.length > 0) {
        warnings.push(`Skipped unsupported: ${invalid.join(", ")}`);
      }
      if (duplicates.length > 0) {
        warnings.push(`Already uploaded: ${duplicates.join(", ")}`);
      }
      if (failed.length > 0) {
        warnings.push(`Failed: ${failed.join("; ")}`);
      }
      if (warnings.length > 0) {
        setError(warnings.join(" | "));
      }

      if (succeeded === 0 && lastSessionId === null) {
        setIsUploading(false);
        setProgress("");
        return;
      }

      setUploadResults({ succeeded, failed });

      if (onUploadComplete) {
        setProgress(`${succeeded} file${succeeded !== 1 ? "s" : ""} uploaded!`);
        setTimeout(() => {
          setIsUploading(false);
          setProgress("");
          setUploadResults(null);
          onUploadComplete();
        }, 1200);
        return;
      }

      if (valid.length === 1 && failed.length === 0 && lastSessionId) {
        setProgress("Done! Redirecting...");
        router.push(`/sessions/${lastSessionId}`);
      } else {
        setProgress(`${succeeded} of ${valid.length} file${valid.length !== 1 ? "s" : ""} uploaded. Redirecting...`);
        setTimeout(() => router.push("/sessions"), 1500);
      }
    },
    [router, onUploadComplete],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) handleFiles(files);
    },
    [handleFiles],
  );

  if (compact) {
    return (
      <div className="w-full">
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-xl p-4 text-center transition-all ${
            isDragging
              ? "border-blue-500 bg-blue-500/10"
              : "border-gray-700 hover:border-gray-500"
          } ${isUploading ? "opacity-60 pointer-events-none" : ""}`}
        >
          {isUploading ? (
            <div className="flex items-center justify-center gap-2 text-blue-400">
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm">{progress}</span>
            </div>
          ) : (
            <label className="cursor-pointer flex items-center justify-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
              <input
                type="file"
                accept=".xrk,.xrz,.csv"
                multiple
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files || []);
                  if (files.length > 0) handleFiles(files);
                  e.target.value = "";
                }}
              />
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Upload files or drag & drop
            </label>
          )}
        </div>
        {error && (
          <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs">
            {error}
          </div>
        )}
      </div>
    );
  }

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
              {isUploading ? progress : "Upload Telemetry Files"}
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
                multiple
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files || []);
                  if (files.length > 0) handleFiles(files);
                  e.target.value = "";
                }}
              />
              Choose Files
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

          {uploadResults && !isUploading && (
            <p className="text-sm text-green-400">
              {uploadResults.succeeded} file{uploadResults.succeeded !== 1 ? "s" : ""} uploaded successfully
              {uploadResults.failed.length > 0 && `, ${uploadResults.failed.length} failed`}
            </p>
          )}

          <p className="text-xs text-gray-500 hidden md:block">
            or drag and drop your files here
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
