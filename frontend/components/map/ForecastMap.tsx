"use client";

import { MapContainer, TileLayer, Rectangle, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { GridPrediction, RiskLevel } from "@/lib/types";

const SEVERITY_COLOR: Record<RiskLevel, string> = {
  low: "#0C6E52",
  moderate: "#A06C10",
  high: "#D4760A",
  severe: "#B84020",
};

const CELL_HALF = 0.5;

const userIcon = L.divIcon({
  className: "",
  html: '<div style="width:14px;height:14px;border-radius:9999px;background:#2563eb;border:2px solid white;box-shadow:0 0 0 2px rgba(37,99,235,0.35)"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

export function ForecastMap({
  cells,
  userPosition,
  onSelectCell,
}: {
  cells: GridPrediction[];
  userPosition?: { lat: number; lon: number } | null;
  onSelectCell?: (cell: GridPrediction) => void;
}) {
  return (
    <MapContainer
      center={[15, 5]}
      zoom={5}
      scrollWheelZoom={true}
      className="absolute inset-0"
      attributionControl={false}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      {cells.map((cell) => (
        <Rectangle
          key={`${cell.lat}-${cell.lon}`}
          bounds={[
            [cell.lat - CELL_HALF, cell.lon - CELL_HALF],
            [cell.lat + CELL_HALF, cell.lon + CELL_HALF],
          ]}
          pathOptions={{
            color: SEVERITY_COLOR[cell.severity],
            weight: 0,
            fillOpacity: 0.35 + cell.probability * 0.25,
          }}
          eventHandlers={{
            click: () => onSelectCell?.(cell),
          }}
        >
          <Popup>
            <div className="text-xs">
              <div className="font-semibold capitalize">{cell.severity} risk</div>
              <div>Probability: {(cell.probability * 100).toFixed(0)}%</div>
              <div>
                {cell.lat.toFixed(1)}, {cell.lon.toFixed(1)}
              </div>
            </div>
          </Popup>
        </Rectangle>
      ))}
      {userPosition && (
        <Marker position={[userPosition.lat, userPosition.lon]} icon={userIcon} />
      )}
    </MapContainer>
  );
}
