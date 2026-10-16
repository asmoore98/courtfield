// A small Leaflet map: job sites (with their on-site radius), crew phones,
// and an optional route. Street tiles come from OpenStreetMap.
import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// markers: [{ lat, lng, label, tone: "on" | "away" | "stale", popup }]
// route: [{ lat, lng, on_site }] drawn as a line with a dot per point
export default function CrewMap({ jobs = [], markers = [], route = [], radius = 400, height = 420, label = "Map" }) {
  const el = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);
  const fitted = useRef("");
  const view = useRef(null); // what to fit to: a point or bounds
  const fit = () => {
    const m = map.current, v = view.current;
    if (!m || !v) return;
    if (v.length === 1) m.setView(v[0], 15);
    else m.fitBounds(L.latLngBounds(v).pad(0.15), { maxZoom: 16 });
  };

  useEffect(() => {
    const m = L.map(el.current, { zoomControl: true, attributionControl: true, scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      // The app sends no referrer by default; OpenStreetMap's tile servers need one.
      referrerPolicy: "strict-origin-when-cross-origin",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(m);
    m.setView([27.3, -80.35], 9);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    let size = "";
    const ro = new ResizeObserver(([e]) => {
      const next = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;
      if (next === size) return;
      const first = !size || size.startsWith("0x") || size.endsWith("x0");
      size = next;
      m.invalidateSize();
      if (first) fit(); // fitting before the map had a size leaves it looking at the wrong place
    });
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      m.remove();
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    const g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    const court = cssVar("--court"), on = cssVar("--under"), away = cssVar("--near"), muted = cssVar("--muted");
    const tone = { on, away, stale: muted };
    const pts = [];
    for (const j of jobs) {
      if (j.lat == null) continue;
      L.circle([j.lat, j.lng], { radius, color: court, weight: 2, dashArray: "6 6", fillColor: court, fillOpacity: 0.08 })
        .bindTooltip(esc(j.name.split(" – ")[0]), { direction: "top" })
        .addTo(g);
      L.circleMarker([j.lat, j.lng], { radius: 4, color: court, fillColor: court, fillOpacity: 1, weight: 1 }).addTo(g);
      pts.push([j.lat, j.lng]);
    }
    if (route.length) {
      L.polyline(route.map((p) => [p.lat, p.lng]), { color: court, weight: 3, opacity: 0.6 }).addTo(g);
      for (const p of route) {
        L.circleMarker([p.lat, p.lng], { radius: 4, weight: 1, color: "#fff", fillColor: p.on_site ? on : away, fillOpacity: 1 })
          .bindTooltip(esc(p.label ?? ""), { direction: "top" })
          .addTo(g);
        pts.push([p.lat, p.lng]);
      }
    }
    for (const mk of markers) {
      const c = tone[mk.tone] ?? court;
      const dot = L.circleMarker([mk.lat, mk.lng], { radius: 10, weight: 3, color: "#fff", fillColor: c, fillOpacity: 1 })
        .bindTooltip(esc(mk.label), { permanent: true, direction: "right", offset: [10, 0], className: "map-label" })
        .addTo(g);
      if (mk.popup) dot.bindPopup(esc(mk.popup));
      pts.push([mk.lat, mk.lng]);
    }
    // Fit to what's shown the first time, and again only if the set of things changes.
    const key = JSON.stringify([jobs.map((j) => j.id), markers.map((x) => x.label), route.length]);
    if (pts.length && key !== fitted.current) {
      fitted.current = key;
      view.current = pts;
      m.invalidateSize();
      fit();
    }
  }, [jobs, markers, route, radius]);

  return <div ref={el} className="crew-map" style={{ height }} role="region" aria-label={label} />;
}
