"use client";

import { WeatherData } from "@/lib/api";

interface WeatherCardProps {
  weather: WeatherData;
}

function WeatherIcon({ label }: { label: string }) {
  if (label.includes("Rain")) {
    return (
      <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 19v2m4-2v2m4-2v2" />
      </svg>
    );
  }
  if (label.includes("Overcast") || label.includes("Cloudy")) {
    return (
      <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
      </svg>
    );
  }
  return (
    <svg className="w-6 h-6 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
    </svg>
  );
}

function GripBadge({ rating }: { rating: string }) {
  const styles = {
    good: "bg-green-500/20 text-green-400 border-green-500/30",
    reduced: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    poor: "bg-red-500/20 text-red-400 border-red-500/30",
  };
  const style = styles[rating as keyof typeof styles] || styles.reduced;

  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase ${style}`}>
      {rating} grip
    </span>
  );
}

function WindArrow({ deg }: { deg: number }) {
  return (
    <svg
      className="w-4 h-4 text-gray-400 inline-block"
      viewBox="0 0 24 24"
      fill="currentColor"
      style={{ transform: `rotate(${deg + 180}deg)` }}
    >
      <path d="M12 2l4 8H8l4-8zm-1 8h2v12h-2V10z" />
    </svg>
  );
}

export default function WeatherCard({ weather }: WeatherCardProps) {
  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700/30 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-700/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <WeatherIcon label={weather.conditions_label} />
          <div>
            <h4 className="text-sm font-semibold text-white">Session Weather</h4>
            <p className="text-[11px] text-gray-500">
              {weather.conditions_label} &middot; via {weather.source}
            </p>
          </div>
        </div>
        <GripBadge rating={weather.grip_assessment.rating} />
      </div>

      <div className="px-4 py-3">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Air Temp</div>
            <div className="text-base font-mono font-bold text-white">{weather.air_temp_f}°F</div>
            <div className="text-[10px] text-gray-500">{weather.air_temp_c}°C</div>
          </div>
          <div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Wind</div>
            <div className="text-base font-mono font-bold text-white flex items-center gap-1">
              {weather.wind_speed_mph} mph
              <WindArrow deg={weather.wind_direction_deg} />
            </div>
            <div className="text-[10px] text-gray-500">{weather.wind_direction_label}</div>
          </div>
          <div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Humidity</div>
            <div className="text-base font-mono font-bold text-white">{weather.humidity_pct}%</div>
            <div className="text-[10px] text-gray-500">{weather.surface_pressure_hpa} hPa</div>
          </div>
        </div>

        {/* Grip assessment notes */}
        {weather.grip_assessment.notes.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-700/30">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5 font-semibold">
              Weather Impact on Driving
            </div>
            <div className="space-y-1">
              {weather.grip_assessment.notes.map((note, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400/60 mt-1.5 flex-shrink-0" />
                  <p className="text-xs text-gray-300">{note}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
