// Offline-first field time.
//
// Every clock-in, task switch and clock-out is written to the phone first
// (localStorage) and queued. The queue syncs whenever there's signal; the
// server treats a resend as a no-op, so retrying is always safe.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, safeGet, safeSet } from "./api";

const ENTRIES_KEY = "cf.entries";   // { [id]: entry }  open entries this phone knows about
const PENDING_KEY = "cf.pending";   // [id]            changed on the phone, not yet synced
const SYNC_EVERY_MS = 15000;

const nowIso = () => new Date().toISOString();
const uuid = () =>
  crypto.randomUUID?.() ??
  "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });

export function getPosition(timeoutMs = 4000) {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000 }
    );
  });
}

const toWire = (e) => ({
  id: e.id, job_id: e.job_id, task_id: e.task_id, worker_id: e.worker_id,
  clock_in: e.clock_in, clock_out: e.clock_out ?? null,
  in_lat: e.in_lat ?? null, in_lng: e.in_lng ?? null,
  out_lat: e.out_lat ?? null, out_lng: e.out_lng ?? null,
  note: e.note ?? "", client_updated_at: e.client_updated_at,
});

export function useFieldTime(meId) {
  // Source of truth lives in refs so a sync always reads the newest changes,
  // even ones made a moment ago; state only drives re-rendering.
  const entriesRef = useRef(safeGet(ENTRIES_KEY, {}));
  // id -> client_updated_at of the version waiting to sync
  const pendingRef = useRef(Object.fromEntries(safeGet(PENDING_KEY, []).map((id) => [id, entriesRef.current[id]?.client_updated_at])));
  const [, rerender] = useState(0);
  const [online, setOnline] = useState(navigator.onLine);
  const [lastSync, setLastSync] = useState(null);
  const [problems, setProblems] = useState([]); // [{ id, worker_id, reason }]
  const busy = useRef(false);
  const again = useRef(false);

  const commit = useCallback(() => {
    safeSet(ENTRIES_KEY, entriesRef.current);
    safeSet(PENDING_KEY, Object.keys(pendingRef.current));
    rerender((n) => n + 1);
  }, []);

  const write = useCallback((changed) => {
    for (const e of changed) {
      entriesRef.current = { ...entriesRef.current, [e.id]: e };
      pendingRef.current = { ...pendingRef.current, [e.id]: e.client_updated_at };
    }
    commit();
  }, [commit]);

  const sync = useCallback(async () => {
    if (busy.current) {
      again.current = true; // run once more when the current sync finishes
      return;
    }
    busy.current = true;
    try {
      const sent = Object.keys(pendingRef.current).map((id) => entriesRef.current[id]).filter(Boolean);
      if (sent.length) {
        const { results } = await api("/api/time/sync", { method: "POST", body: { entries: sent.map(toWire) } });
        const sentVersion = Object.fromEntries(sent.map((e) => [e.id, e.client_updated_at]));
        const pending = { ...pendingRef.current };
        const entries = { ...entriesRef.current };
        const rejected = [];
        for (const r of results) {
          // Only clear the queue if nothing changed on the phone since we sent it.
          if (pending[r.id] !== sentVersion[r.id]) continue;
          delete pending[r.id];
          if (r.status === "rejected") {
            rejected.push({ ...r, worker_id: entries[r.id]?.worker_id });
            delete entries[r.id];
          }
        }
        pendingRef.current = pending;
        entriesRef.current = entries;
        if (rejected.length) setProblems((p) => [...p, ...rejected]);
      }
      // Pull who is clocked in anywhere right now (another phone may have
      // changed it). Unsynced changes on this phone win until they sync.
      const open = await api("/api/time?open_only=true");
      const queued = pendingRef.current;
      const next = {};
      for (const [id, e] of Object.entries(entriesRef.current)) if (id in queued) next[id] = e;
      for (const e of open) if (!(e.id in queued)) next[e.id] = e;
      entriesRef.current = next;
      setOnline(true);
      setLastSync(new Date());
    } catch (err) {
      if (err.status === 0) setOnline(false);
    } finally {
      busy.current = false;
      commit();
      if (again.current) {
        again.current = false;
        setTimeout(sync, 0);
      }
    }
  }, [commit]);

  useEffect(() => {
    sync();
    const t = setInterval(sync, SYNC_EVERY_MS);
    const on = () => sync();
    window.addEventListener("online", on);
    return () => {
      clearInterval(t);
      window.removeEventListener("online", on);
    };
  }, [sync]);

  const entries = entriesRef.current;
  const openFor = useCallback(
    (workerId) => Object.values(entries).find((e) => e.worker_id === workerId && !e.clock_out),
    [entries]
  );

  // Start (or switch) these workers onto a task. Anyone already on a task is
  // clocked out of it at the same moment, so time never overlaps.
  const startTask = useCallback(
    async (workerIds, jobId, taskId) => {
      const pos = await getPosition();
      const at = nowIso();
      const changed = [];
      for (const wid of workerIds) {
        const cur = openFor(wid);
        if (cur && cur.task_id === taskId && cur.job_id === jobId) continue;
        if (cur) changed.push({ ...cur, clock_out: at, out_lat: pos?.lat, out_lng: pos?.lng, client_updated_at: at });
        changed.push({
          id: uuid(), job_id: jobId, task_id: taskId, worker_id: wid, entered_by_id: meId, clock_in: at,
          in_lat: pos?.lat, in_lng: pos?.lng, client_updated_at: at,
        });
      }
      write(changed);
      setTimeout(sync, 0);
    },
    [openFor, write, sync, meId]
  );

  const clockOut = useCallback(
    async (workerIds) => {
      const pos = await getPosition();
      const at = nowIso();
      const changed = workerIds
        .map(openFor)
        .filter(Boolean)
        .map((cur) => ({ ...cur, clock_out: at, out_lat: pos?.lat, out_lng: pos?.lng, client_updated_at: at }));
      write(changed);
      setTimeout(sync, 0);
    },
    [openFor, write, sync]
  );

  const dismissProblem = (id) => setProblems((p) => p.filter((x) => x.id !== id));

  const pendingCount = Object.keys(pendingRef.current).length;
  // Someone this phone clocked in is on the clock (drives location sharing).
  const myCrewOnClock = Object.values(entries).some((e) => !e.clock_out && e.entered_by_id === meId);
  return { myCrewOnClock, openFor, startTask, clockOut, sync, online, lastSync, pendingCount, problems, dismissProblem };
}
