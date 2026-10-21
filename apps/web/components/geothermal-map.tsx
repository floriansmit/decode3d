"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Minus, Plus } from "lucide-react";

type GeoPoint = { lon: number; lat: number; valid_mask: number } & Record<string, number>;
type Well = { name: string; lon: number; lat: number; role: "conditioning" | "tops_only" };
type FocusLocation = { lon: number; lat: number; label: string; zoom?: number } | null;
type View = { lon: number; lat: number; zoom: number };
type Size = { width: number; height: number };
export type CulturalArea = { id: string; name: string; lon: number; lat: number; geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] }; heat_delivery_tj_2024: number | null; co2_kg_gj_2024: number | null; statistics_name: string | null };
export type CulturalSite = { id: string; name: string; lon: number; lat: number; kind: "industry" | "heat_plant"; activity_code: string; activity: string; source_year: number };
export type CulturalData = { model_version: string; district_heating_areas: CulturalArea[]; sites: CulturalSite[]; summary: Record<string, number>; notes: string };

const TILE_SIZE = 256;
const MIN_ZOOM = 6;
const MAX_ZOOM = 17;
const OSM_TILE_URL = "https://tile.openstreetmap.org";

function clampLat(lat: number) { return Math.max(-85.05112878, Math.min(85.05112878, lat)); }
function project(lon: number, lat: number, zoom: number) {
  const scale = TILE_SIZE * 2 ** zoom;
  const sin = Math.sin(clampLat(lat) * Math.PI / 180);
  return { x: (lon + 180) / 360 * scale, y: (.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale };
}
function unproject(x: number, y: number, zoom: number) {
  const scale = TILE_SIZE * 2 ** zoom;
  const lon = x / scale * 360 - 180;
  const n = Math.PI - 2 * Math.PI * y / scale;
  return { lon, lat: 180 / Math.PI * Math.atan(Math.sinh(n)) };
}

export function GeothermalMap({ points, wells, selected, range, property, palette, showBasemap, focusLocation, cultural, showDistrictHeating = false, showHeatDelivery = false, showIndustry = false, showHeatPlants = false, onSelect }:
  { points: GeoPoint[]; wells: Well[]; selected: GeoPoint | null; range: number[]; property: string; palette: string[]; showBasemap: boolean; focusLocation: FocusLocation; cultural?: CulturalData | null; showDistrictHeating?: boolean; showHeatDelivery?: boolean; showIndustry?: boolean; showHeatPlants?: boolean; onSelect: (point: GeoPoint) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pointers = useRef(new globalThis.Map<number, { x: number; y: number }>());
  const dragRef = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const pinchRef = useRef<{ distance: number; zoom: number } | null>(null);
  const fitted = useRef(false);
  const [size, setSize] = useState<Size>({ width: 900, height: 650 });
  const [view, setView] = useState<View>({ lon: 10.08, lat: 56.55, zoom: 8 });
  const [selectedCultural, setSelectedCultural] = useState<CulturalArea | CulturalSite | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: entry.contentRect.height }));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const modelBounds = useMemo(() => points.length ? {
    minLon: Math.min(...points.map((p) => p.lon)), maxLon: Math.max(...points.map((p) => p.lon)),
    minLat: Math.min(...points.map((p) => p.lat)), maxLat: Math.max(...points.map((p) => p.lat)),
  } : null, [points]);

  const fitModel = useCallback(() => {
    if (!modelBounds || !size.width || !size.height) return;
    const lon = (modelBounds.minLon + modelBounds.maxLon) / 2, lat = (modelBounds.minLat + modelBounds.maxLat) / 2;
    let zoom = MIN_ZOOM;
    for (let candidate = MAX_ZOOM; candidate >= MIN_ZOOM; candidate--) {
      const nw = project(modelBounds.minLon, modelBounds.maxLat, candidate);
      const se = project(modelBounds.maxLon, modelBounds.minLat, candidate);
      if (se.x - nw.x <= size.width - 90 && se.y - nw.y <= size.height - 90) { zoom = candidate; break; }
    }
    setView({ lon, lat, zoom });
  }, [modelBounds, size]);

  useEffect(() => { if (!fitted.current && modelBounds && size.width) { fitted.current = true; fitModel(); } }, [fitModel, modelBounds, size.width]);
  useEffect(() => { if (focusLocation) setView({ lon: focusLocation.lon, lat: focusLocation.lat, zoom: focusLocation.zoom ?? 14 }); }, [focusLocation]);

  const center = project(view.lon, view.lat, view.zoom);
  const topLeft = { x: center.x - size.width / 2, y: center.y - size.height / 2 };
  const tiles = useMemo(() => {
    if (!showBasemap) return [];
    const count = 2 ** view.zoom, output = [];
    const minX = Math.floor(topLeft.x / TILE_SIZE), maxX = Math.floor((topLeft.x + size.width) / TILE_SIZE);
    const minY = Math.floor(topLeft.y / TILE_SIZE), maxY = Math.floor((topLeft.y + size.height) / TILE_SIZE);
    for (let y = minY; y <= maxY; y++) for (let x = minX; x <= maxX; x++) {
      if (y >= 0 && y < count) output.push({ key: `${view.zoom}-${x}-${y}`, x, y, tileX: ((x % count) + count) % count });
    }
    return output;
  }, [showBasemap, size, topLeft.x, topLeft.y, view.zoom]);

  const screen = (point: { lon: number; lat: number }) => {
    const p = project(point.lon, point.lat, view.zoom);
    return { x: p.x - topLeft.x, y: p.y - topLeft.y };
  };
  const areaPath = (area: CulturalArea) => {
    const polygons = area.geometry.type === "Polygon" ? [area.geometry.coordinates as number[][][]] : area.geometry.coordinates as number[][][][];
    return polygons.map((polygon) => polygon.map((ring) => ring.map(([lon, lat], index) => { const p = screen({ lon, lat }); return `${index ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`; }).join("") + "Z").join("")).join("");
  };
  const heatValues = cultural?.district_heating_areas.map((area) => area.heat_delivery_tj_2024 ?? 0).filter(Boolean).sort((a, b) => a - b) ?? [];
  const heatMax = heatValues[Math.floor(heatValues.length * .9)] ?? 1;
  const cellSize = useMemo(() => {
    if (points.length < 2) return { width: 12, height: 12 };
    const rowLength = points.findIndex((point, index) => index > 0 && point.lon < points[index - 1].lon);
    const origin = project(points[0].lon, points[0].lat, view.zoom);
    const right = project(points[1].lon, points[1].lat, view.zoom);
    const nextRow = project(points[rowLength > 0 ? rowLength : 1].lon, points[rowLength > 0 ? rowLength : 1].lat, view.zoom);
    return {
      width: Math.max(5, Math.hypot(right.x - origin.x, right.y - origin.y) + 1.2),
      height: Math.max(5, Math.hypot(nextRow.x - origin.x, nextRow.y - origin.y) + 1.2),
    };
  }, [points, view.zoom]);

  const setZoom = (zoom: number, anchor?: { x: number; y: number }) => {
    const nextZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(zoom)));
    if (nextZoom === view.zoom) return;
    const cursor = anchor ?? { x: size.width / 2, y: size.height / 2 };
    const underCursor = unproject(topLeft.x + cursor.x, topLeft.y + cursor.y, view.zoom);
    const nextCursorWorld = project(underCursor.lon, underCursor.lat, nextZoom);
    const nextCenter = unproject(nextCursorWorld.x - cursor.x + size.width / 2, nextCursorWorld.y - cursor.y + size.height / 2, nextZoom);
    setView({ ...nextCenter, zoom: nextZoom });
  };
  const onWheel = (event: React.WheelEvent) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    setZoom(view.zoom + (event.deltaY < 0 ? 1 : -1), { x: event.clientX - rect.left, y: event.clientY - rect.top });
  };
  const onPointerDown = (event: React.PointerEvent) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    dragRef.current = { x: event.clientX, y: event.clientY, moved: false };
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinchRef.current = { distance: Math.hypot(a.x - b.x, a.y - b.y), zoom: view.zoom };
    }
  };
  const onPointerMove = (event: React.PointerEvent) => {
    if (!pointers.current.has(event.pointerId)) return;
    const previous = pointers.current.get(event.pointerId)!;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 2 && pinchRef.current) {
      const [a, b] = [...pointers.current.values()];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      if (distance > pinchRef.current.distance * 1.35) { setZoom(pinchRef.current.zoom + 1); pinchRef.current = { distance, zoom: view.zoom + 1 }; }
      else if (distance < pinchRef.current.distance / 1.35) { setZoom(pinchRef.current.zoom - 1); pinchRef.current = { distance, zoom: view.zoom - 1 }; }
      return;
    }
    const dx = event.clientX - previous.x, dy = event.clientY - previous.y;
    if (Math.abs(dx) + Math.abs(dy) > 0) {
      if (dragRef.current) dragRef.current.moved = dragRef.current.moved || Math.abs(event.clientX - dragRef.current.x) + Math.abs(event.clientY - dragRef.current.y) > 5;
      setView((current) => {
        const currentCenter = project(current.lon, current.lat, current.zoom);
        const next = unproject(currentCenter.x - dx, currentCenter.y - dy, current.zoom);
        return { ...current, ...next };
      });
    }
  };
  const onPointerUp = (event: React.PointerEvent) => {
    const moved = dragRef.current?.moved;
    pointers.current.delete(event.pointerId); pinchRef.current = null;
    if (!moved && pointers.current.size === 0) {
      const rect = event.currentTarget.getBoundingClientRect();
      const clicked = unproject(topLeft.x + event.clientX - rect.left, topLeft.y + event.clientY - rect.top, view.zoom);
      let nearest: GeoPoint | null = null, distance = Infinity;
      for (const point of points) { const d = (point.lon - clicked.lon) ** 2 + (point.lat - clicked.lat) ** 2; if (d < distance) { nearest = point; distance = d; } }
      if (nearest && distance < .00045) onSelect(nearest);
    }
    dragRef.current = null;
  };

  return <div ref={containerRef} className={`slippy-map ${showBasemap ? "with-basemap" : ""}`} onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onDoubleClick={(event) => { const rect = event.currentTarget.getBoundingClientRect(); setZoom(view.zoom + 1, { x: event.clientX - rect.left, y: event.clientY - rect.top }); }}>
    <div className="tile-layer">{tiles.map((tile) => <img key={tile.key} src={`${OSM_TILE_URL}/${view.zoom}/${tile.tileX}/${tile.y}.png`} alt="" draggable={false} width={TILE_SIZE} height={TILE_SIZE} style={{ left: tile.x * TILE_SIZE - topLeft.x, top: tile.y * TILE_SIZE - topLeft.y }} />)}</div>
    <svg className="geology-overlay" width={size.width} height={size.height} aria-label="Interactive geothermal model overlay">
      {points.map((point, index) => { const p = screen(point), n = (point[property] - range[0]) / Math.max(range[1] - range[0], .0001), isSelected = selected?.lon === point.lon && selected?.lat === point.lat; return <rect key={index} className="model-cell" x={p.x - cellSize.width / 2} y={p.y - cellSize.height / 2} width={cellSize.width} height={cellSize.height} rx=".75" fill={point.valid_mask ? ramp(palette, n) : "#30343e"} opacity={point.valid_mask ? (showBasemap ? .72 : .94) : .22} stroke={isSelected ? "#fff1b6" : "rgba(17,21,28,.28)"} strokeWidth={isSelected ? 2.5 : .55} onPointerUp={() => { if (!dragRef.current?.moved) onSelect(point); }} />; })}
      {cultural && (showDistrictHeating || showHeatDelivery) && <g className="district-heating-areas">{cultural.district_heating_areas.map((area) => {
        const intensity = Math.min(1, Math.sqrt((area.heat_delivery_tj_2024 ?? 0) / heatMax));
        return <path key={area.id} d={areaPath(area)} fillRule="evenodd" fill={showHeatDelivery && area.heat_delivery_tj_2024 ? `rgba(230,107,52,${(.15 + intensity * .38).toFixed(2)})` : "rgba(57,178,190,.13)"} stroke={showHeatDelivery ? "rgba(255,190,108,.8)" : "rgba(111,224,230,.8)"} strokeWidth="1.2" />;
      })}</g>}
      {cultural && (showDistrictHeating || showHeatDelivery) && view.zoom >= 9 && <g className="network-centres">{cultural.district_heating_areas.map((area) => { const p = screen(area); return <circle key={area.id} cx={p.x} cy={p.y} r="3.5" onPointerDown={(event) => event.stopPropagation()} onPointerUp={(event) => { event.stopPropagation(); setSelectedCultural(area); }} />; })}</g>}
      {wells.map((well) => { const p = screen(well); return <g key={well.name} className={`well-marker ${well.role}`}><circle cx={p.x} cy={p.y} r={well.role === "conditioning" ? 6 : 4} /><path d={`M${p.x} ${p.y - 9}v-9`} /><text x={p.x + 9} y={p.y - 10}>{well.name}</text></g>; })}
      {cultural?.sites.filter((site) => site.kind === "industry" ? showIndustry : showHeatPlants).map((site) => { const p = screen(site); return <g key={site.id} className={`cultural-site ${site.kind}`} transform={`translate(${p.x} ${p.y})`} onPointerDown={(event) => event.stopPropagation()} onPointerUp={(event) => { event.stopPropagation(); setSelectedCultural(site); }}><circle r="8" /><path d={site.kind === "heat_plant" ? "M-3 4V-4h2v3l2-2v2l2-2v7Z" : "M-4 4V-4h3v3l3-2v7Z"} /></g>; })}
      {focusLocation && (() => { const p = screen(focusLocation); return <g className="address-marker"><path d={`M${p.x} ${p.y}c-18-22-13-43 0-43s18 21 0 43Z`} /><circle cx={p.x} cy={p.y - 29} r="5" /></g>; })()}
      {selected && (() => { const p = screen(selected); return <circle cx={p.x} cy={p.y} r="12" className="selected-cell" />; })()}
    </svg>
    {selectedCultural && <div className="cultural-popup" onPointerDown={(event) => event.stopPropagation()} onPointerUp={(event) => event.stopPropagation()}><button aria-label="Close" onClick={() => setSelectedCultural(null)}>×</button><span>{"kind" in selectedCultural ? selectedCultural.kind === "industry" ? "Industrial heat candidate" : "Heat-production plant" : "District-heating area"}</span><strong>{selectedCultural.name}</strong>{"kind" in selectedCultural ? <p>{selectedCultural.activity}<small>PRTR {selectedCultural.source_year} · {selectedCultural.activity_code}</small></p> : <p>{selectedCultural.heat_delivery_tj_2024 ? `${selectedCultural.heat_delivery_tj_2024.toLocaleString("en-GB")} TJ delivered in 2024` : "No linked 2024 network statistic"}<small>{selectedCultural.co2_kg_gj_2024 != null ? `${selectedCultural.co2_kg_gj_2024} kg CO₂/GJ` : "Official Plandata supply area"}</small></p>}</div>}
    <div className="map-controls" onPointerDown={(event) => event.stopPropagation()} onPointerUp={(event) => event.stopPropagation()}><button aria-label="Zoom in" onClick={(e) => { e.stopPropagation(); setZoom(view.zoom + 1); }}><Plus /></button><button aria-label="Zoom out" onClick={(e) => { e.stopPropagation(); setZoom(view.zoom - 1); }}><Minus /></button><button aria-label="Fit geological model" title="Fit geological model" onClick={(e) => { e.stopPropagation(); fitModel(); }}><Crosshair /></button></div>
    <div className="zoom-readout">z{view.zoom}</div>
    {showBasemap && <div className="osm-attribution" onPointerDown={(event) => event.stopPropagation()} onPointerUp={(event) => event.stopPropagation()}>© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · <a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noreferrer">Report map issue</a></div>}
  </div>;
}

function ramp(palette: string[], value: number) {
  const t = Math.max(0, Math.min(.999, value)), index = Math.floor(t * (palette.length - 1)), local = t * (palette.length - 1) - index;
  const a = palette[index].match(/\w\w/g)!.map((v) => parseInt(v, 16));
  const b = palette[index + 1].match(/\w\w/g)!.map((v) => parseInt(v, 16));
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * local)).join(",")})`;
}
