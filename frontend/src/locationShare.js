// Share this phone's location with the office while anyone it clocked in is
// on the clock. Nothing is recorded off the clock, and the server drops any
// ping that doesn't fall inside clocked time this person entered.
//
// A web app only gets GPS while it's open on screen, so pings stop when the
// phone locks and pick up again when the app is opened. Pings are queued on
// the phone and sent when there's signal, after the time entries they belong
// to have synced.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, safeGet, safeSet } from "./api";

const QUEUE_KEY = "cf.pings";
const MAX_QUEUED = 3000;
const PING_EVERY_MS = 3 * 60 * 1000; // at least this often while the app is open
const MOVED_M = 150;                // or sooner when the phone has moved this far
const FLUSH_EVERY_MS = 30000;

const uuid = () =>
  crypto.randomUUID?.() ??
  "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });

function meters(a, b) {
  const r = 6371000, rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

export function useLocationSharing({ active, enabled, canFlush }) {
  const queue = useRef(safeGet(QUEUE_KEY, []));
  const last = useRef(null); // { t, lat, lng } of the last recorded ping
  const sending = useRef(false);
  const [permission, setPermission] = useState("unknown"); // unknown | granted | denied | unsupported
  const [lastAt, setLastAt] = useState(null);
  const [queued, setQueued] = useState(queue.current.length);

  const save = () => {
    safeSet(QUEUE_KEY, queue.current);
    setQueued(queue.current.length);
  };

  const flush = useCallback(async () => {
    if (sending.current || !canFlush || !queue.current.length) return;
    sending.current = true;
    try {
      while (queue.current.length) {
        const batch = queue.current.slice(0, 500);
        const { saved, dropped } = await api("/api/locations", { method: "POST", body: { pings: batch } });
        const done = new Set([...saved, ...dropped]);
        queue.current = queue.current.filter((p) => !done.has(p.id));
        save();
        if (!done.size) break;
      }
    } catch {
      // no signal; try again later
    } finally {
      sending.current = false;
    }
  }, [canFlush]);

  const record = useCallback(
    (pos, force = false) => {
      const p = { lat: pos.coords.latitude, lng: pos.coords.longitude, t: Date.now() };
      const prev = last.current;
      if (!force && prev && p.t - prev.t < PING_EVERY_MS && meters(prev, p) < MOVED_M) return;
      last.current = p;
      queue.current = [
        ...queue.current,
        { id: uuid(), recorded_at: new Date(p.t).toISOString(), lat: p.lat, lng: p.lng, accuracy_m: Math.round(pos.coords.accuracy ?? 0) || null },
      ].slice(-MAX_QUEUED);
      save();
      setLastAt(new Date(p.t));
      setPermission("granted");
    },
    []
  );

  useEffect(() => {
    if (!enabled) return;
    if (!navigator.geolocation) return setPermission("unsupported");
    navigator.permissions?.query({ name: "geolocation" }).then(
      (s) => {
        const set = () => setPermission(s.state === "denied" ? "denied" : s.state === "granted" ? "granted" : "unknown");
        set();
        s.onchange = set;
      },
      () => {}
    );
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !active || !navigator.geolocation) return;
    const onErr = (e) => e.code === 1 && setPermission("denied");
    const opts = { enableHighAccuracy: true, maximumAge: 30000, timeout: 20000 };
    const take = (force) => navigator.geolocation.getCurrentPosition((p) => record(p, force), onErr, opts);
    const watch = navigator.geolocation.watchPosition((p) => record(p), onErr, opts);
    take(true);
    // watchPosition only fires on movement; a phone sitting on site still checks in.
    const t = setInterval(() => document.visibilityState === "visible" && take(false), 60000);
    const onVisible = () => document.visibilityState === "visible" && take(true);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      navigator.geolocation.clearWatch(watch);
      clearInterval(t);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled, active, record]);

  useEffect(() => {
    if (!enabled) return;
    flush();
    const t = setInterval(flush, FLUSH_EVERY_MS);
    window.addEventListener("online", flush);
    return () => {
      clearInterval(t);
      window.removeEventListener("online", flush);
    };
  }, [enabled, flush, queued]);

  return { permission, lastAt, queued };
}
