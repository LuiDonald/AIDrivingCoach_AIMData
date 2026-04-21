"use client";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { getTrackMap, TrackMapData } from "@/lib/api";

interface TrackMapProps {
  token: string;
  lapNumber: number | null;
  highlightDistance?: number | null;
  highlightRange?: [number, number] | null;
  onDistanceSelect?: (distance_m: number) => void;
}

function speedToColor(speed: number, min: number, max: number): string {
  const range = max - min || 1;
  const t = Math.max(0, Math.min(1, (speed - min) / range));
  if (t < 0.5) {
    const r = 255;
    const g = Math.round(t * 2 * 255);
    return `rgb(${r},${g},0)`;
  }
  const r = Math.round((1 - (t - 0.5) * 2) * 255);
  const g = 255;
  return `rgb(${r},${g},0)`;
}

export default function TrackMap({ token, lapNumber, highlightDistance, highlightRange, onDistanceSelect }: TrackMapProps) {
  const [data, setData] = useState<TrackMapData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!lapNumber) return;
    setLoading(true);
    setError(null);
    getTrackMap(token, lapNumber)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token, lapNumber]);

  const { projected, viewBox, cornerPositions } = useMemo(() => {
    if (!data || data.points.length === 0)
      return { projected: [], viewBox: "0 0 400 400", cornerPositions: [] };

    const pts = data.points;
    const centerLat = (Math.min(...pts.map((p) => p.lat)) + Math.max(...pts.map((p) => p.lat))) / 2;
    const cosLat = Math.cos((centerLat * Math.PI) / 180);

    const xs = pts.map((p) => (p.lon - pts[0].lon) * cosLat * 111320);
    const ys = pts.map((p) => (p.lat - pts[0].lat) * 111320);

    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    const padding = 35;
    const size = 400;
    const scale = Math.min((size - padding * 2) / rangeX, (size - padding * 2) / rangeY);
    const offsetX = (size - rangeX * scale) / 2;
    const offsetY = (size - rangeY * scale) / 2;

    const projected = pts.map((p, i) => ({
      x: (xs[i] - minX) * scale + offsetX,
      y: size - ((ys[i] - minY) * scale + offsetY),
      speed: p.speed_mph,
      distance: p.distance_m,
      time_ms: p.time_ms,
    }));

    const cornerPositions = data.corners.map((c) => {
      const cx = (c.lon - pts[0].lon) * cosLat * 111320;
      const cy = (c.lat - pts[0].lat) * 111320;
      return {
        ...c,
        x: (cx - minX) * scale + offsetX,
        y: size - ((cy - minY) * scale + offsetY),
      };
    });

    return {
      projected,
      viewBox: `0 0 ${size} ${size}`,
      cornerPositions,
    };
  }, [data]);

  const handleSvgInteraction = useCallback(
    (e: React.MouseEvent<SVGSVGElement> | React.TouchEvent<SVGSVGElement>) => {
      if (!svgRef.current || projected.length === 0) return;
      const svg = svgRef.current;
      const rect = svg.getBoundingClientRect();

      let clientX: number, clientY: number;
      if ("touches" in e) {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
      } else {
        clientX = e.clientX;
        clientY = e.clientY;
      }

      const scaleX = 400 / rect.width;
      const scaleY = 400 / rect.height;
      const svgX = (clientX - rect.left) * scaleX;
      const svgY = (clientY - rect.top) * scaleY;

      let minDist = Infinity;
      let nearestIdx = 0;
      for (let i = 0; i < projected.length; i++) {
        const dx = projected[i].x - svgX;
        const dy = projected[i].y - svgY;
        const d = dx * dx + dy * dy;
        if (d < minDist) {
          minDist = d;
          nearestIdx = i;
        }
      }
      return nearestIdx;
    },
    [projected],
  );

  const handleMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement> | React.TouchEvent<SVGSVGElement>) => {
      const idx = handleSvgInteraction(e);
      if (idx !== undefined) setHoveredIdx(idx);
    },
    [handleSvgInteraction],
  );

  const handleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      const idx = handleSvgInteraction(e);
      if (idx !== undefined) {
        setSelectedIdx(idx);
        if (onDistanceSelect) {
          onDistanceSelect(projected[idx].distance);
        }
      }
    },
    [handleSvgInteraction, onDistanceSelect, projected],
  );

  const externalIdx = useMemo(() => {
    if (highlightDistance == null || projected.length === 0) return null;
    let best = 0;
    let bestDiff = Math.abs(projected[0].distance - highlightDistance);
    for (let i = 1; i < projected.length; i++) {
      const diff = Math.abs(projected[i].distance - highlightDistance);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = i;
      }
    }
    return best;
  }, [highlightDistance, projected]);

  if (!lapNumber) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/30 text-center text-gray-500 text-sm">
        Select a lap to view track map
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/30 flex items-center justify-center text-gray-400 text-sm">
        <svg className="animate-spin w-4 h-4 mr-2 text-blue-500" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading track...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/30 text-center text-yellow-400 text-xs">
        {error.includes("No GPS")
          ? "GPS data not available. Upload .xrk/.xrz with GPS for the track map."
          : error}
      </div>
    );
  }

  if (!data || projected.length === 0) return null;

  const activeIdx = selectedIdx ?? hoveredIdx ?? externalIdx;
  const activePoint = activeIdx !== null ? projected[activeIdx] : null;

  return (
    <div className="bg-gray-800/50 rounded-xl border border-gray-700/30 overflow-hidden">
      <div className="px-3 pt-2 pb-0.5 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-white">Track Map</h3>
        {activePoint && (
          <div className="flex gap-2 text-[11px] text-gray-400">
            <span className="font-mono">{activePoint.speed.toFixed(0)} mph</span>
            <span>{activePoint.distance.toFixed(0)}m</span>
          </div>
        )}
      </div>

      <svg
        ref={svgRef}
        viewBox={viewBox}
        className="w-full touch-none cursor-crosshair"
        style={{ aspectRatio: "1 / 1" }}
        onMouseMove={handleMove}
        onMouseLeave={() => setHoveredIdx(null)}
        onClick={handleClick}
        onTouchMove={handleMove}
      >
        <rect width="400" height="400" fill="transparent" />

        {projected.map((pt, i) => {
          if (i === 0) return null;
          const prev = projected[i - 1];
          return (
            <line
              key={i}
              x1={prev.x}
              y1={prev.y}
              x2={pt.x}
              y2={pt.y}
              stroke={speedToColor(pt.speed, data.min_speed, data.max_speed)}
              strokeWidth={3}
              strokeLinecap="round"
              opacity={highlightRange ? 0.3 : 1}
            />
          );
        })}

        {highlightRange && projected.map((pt, i) => {
          if (i === 0) return null;
          const prev = projected[i - 1];
          const inRange = pt.distance >= highlightRange[0] && pt.distance <= highlightRange[1];
          if (!inRange) return null;
          return (
            <line
              key={`hl-${i}`}
              x1={prev.x}
              y1={prev.y}
              x2={pt.x}
              y2={pt.y}
              stroke="#22D3EE"
              strokeWidth={7}
              strokeLinecap="round"
              opacity={0.7}
            />
          );
        })}

        {cornerPositions.map((c) => (
          <g key={c.corner_id}>
            <circle cx={c.x} cy={c.y} r={11} fill="rgba(0,0,0,0.7)" stroke="#6B7280" strokeWidth={1} />
            <text
              x={c.x}
              y={c.y + 1}
              textAnchor="middle"
              dominantBaseline="central"
              fill="white"
              fontSize="8"
              fontWeight="bold"
            >
              {c.label || c.corner_id}
            </text>
          </g>
        ))}

        {projected.length > 0 && (
          <g>
            <rect
              x={projected[0].x - 7}
              y={projected[0].y - 4}
              width={14}
              height={8}
              fill="white"
              rx={2}
            />
            <text
              x={projected[0].x}
              y={projected[0].y + 1}
              textAnchor="middle"
              dominantBaseline="central"
              fill="black"
              fontSize="5"
              fontWeight="bold"
            >
              S/F
            </text>
          </g>
        )}

        {activePoint && (
          <g>
            {externalIdx != null && activeIdx === externalIdx && (
              <circle cx={activePoint.x} cy={activePoint.y} r={14} fill="#F59E0B" opacity={0.25}>
                <animate attributeName="r" values="10;16;10" dur="1.5s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.3;0.1;0.3" dur="1.5s" repeatCount="indefinite" />
              </circle>
            )}
            <circle cx={activePoint.x} cy={activePoint.y} r={7} fill="white" opacity={0.3} />
            <circle
              cx={activePoint.x}
              cy={activePoint.y}
              r={externalIdx != null && activeIdx === externalIdx ? 6 : 4}
              fill={externalIdx != null && activeIdx === externalIdx ? "#F59E0B" : "#3B82F6"}
              stroke="white"
              strokeWidth={2}
            />
          </g>
        )}
      </svg>

      <div className="px-3 py-1.5 flex items-center gap-2 text-[10px] text-gray-500">
        <span>{data.min_speed.toFixed(0)}</span>
        <div
          className="flex-1 h-1.5 rounded-full"
          style={{
            background: "linear-gradient(to right, rgb(255,0,0), rgb(255,255,0), rgb(0,255,0))",
          }}
        />
        <span>{data.max_speed.toFixed(0)} mph</span>
      </div>
    </div>
  );
}
