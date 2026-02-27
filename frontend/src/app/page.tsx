import FileUpload from "@/components/FileUpload";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg text-center mb-8">
        <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          AIM Analyzer
        </h1>
        <p className="text-gray-400 text-sm md:text-base">
          AI-powered driving coach for AIM SOLO &amp; SOLO DL
        </p>
      </div>
      <FileUpload />
      <div className="mt-12 text-center">
        <p className="text-xs text-gray-600 max-w-md">
          Upload your telemetry file from AIM Race Studio (.xrk, .xrz) or exported CSV.
          Your data is analyzed locally and never shared.
        </p>
      </div>
    </div>
  );
}
