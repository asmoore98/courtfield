// A job's material list: planned on the estimate, sent from the warehouse,
// brought back, and used. The warehouse and GM log sends and returns here;
// crew leads see the same list read-only.
import { Fragment, useCallback, useEffect, useState } from "react";
import { api, safeGet, safeSet } from "./api";

const fmt = (n) => (Math.round(n * 100) / 100).toLocaleString("en-US", { maximumFractionDigits: 2 });
const money = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const STATUS = {
  not_sent: ["Not sent", "s-none"],
  partly_sent: ["Partly sent", "s-wait"],
  sent: ["Sent", "s-ok"],
  over_sent: ["More than planned", "s-wait"],
};
const timeLabel = (iso) => new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

function MoveForm({ jobId, row, kind, items, onDone, onCancel }) {
  const outNow = row ? row.sent - row.returned : 0;
  const [qty, setQty] = useState(() => (kind === "to_job" ? (row?.left_to_send ? String(row.left_to_send) : "") : outNow ? String(outNow) : ""));
  const [lot, setLot] = useState("");
  const [note, setNote] = useState("");
  const [itemId, setItemId] = useState("");
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const extra = !row; // something not on the list

  async function save(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const body = { kind, job_id: jobId, quantity: Number(qty), lot_number: lot, note };
    if (row) body.row_key = row.key;
    else if (itemId) body.item_id = itemId;
    else Object.assign(body, { description: name, unit });
    try {
      await api("/api/stock/moves", { method: "POST", body });
      onDone();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const unitShown = row?.unit || items.find((i) => i.id === itemId)?.unit || unit;
  return (
    <form className="timeform" onSubmit={save}>
      <h4>
        {kind === "to_job" ? "Send to job" : "Log what came back"}
        {row ? `: ${row.description}` : ""}
      </h4>
      {kind === "from_job" && row && <p className="help">{fmt(outNow)} {row.unit} is out on this job now.</p>}
      <div className="tf-grid">
        {extra && (
          <label>
            Item
            <select value={itemId} onChange={(e) => setItemId(e.target.value)}>
              <option value="">Not on the price list…</option>
              {items.filter((i) => i.category === "material").map((i) => (
                <option key={i.id} value={i.id}>{i.name}{i.on_hand != null ? ` (${fmt(i.on_hand)} ${i.unit} on hand)` : ""}</option>
              ))}
            </select>
          </label>
        )}
        {extra && !itemId && (
          <>
            <label>
              Name
              <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Painter's tape" />
            </label>
            <label>
              Unit
              <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="roll" maxLength={20} />
            </label>
          </>
        )}
        <label>
          Quantity{unitShown ? ` (${unitShown})` : ""}
          <input type="number" inputMode="decimal" min="0" step="any" required value={qty} onChange={(e) => setQty(e.target.value)} />
        </label>
        {kind === "to_job" && (
          <label>
            Lot or batch number
            <input value={lot} onChange={(e) => setLot(e.target.value)} placeholder="From the pail label" maxLength={60} />
          </label>
        )}
        <label className="tf-reason">
          Note (optional)
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder={kind === "to_job" ? "e.g. Truck 2, Monday load" : "e.g. 1 pail opened, half full"} />
        </label>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="tf-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={busy}>{busy ? "Saving…" : kind === "to_job" ? "Log as sent" : "Log as returned"}</button>
      </div>
    </form>
  );
}

function History({ jobId, canVoid, version, onChanged }) {
  const [moves, setMoves] = useState(null);
  const [voiding, setVoiding] = useState(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState(null);
  useEffect(() => {
    api(`/api/jobs/${jobId}/materials/moves`).then(setMoves).catch(() => setMoves([]));
  }, [jobId, version]);
  if (!moves) return <p className="help">Loading history…</p>;
  if (!moves.length) return <p className="help">Nothing has gone out to this job yet.</p>;

  async function doVoid(e) {
    e.preventDefault();
    setError(null);
    try {
      await api(`/api/stock/moves/${voiding}/void`, { method: "POST", body: { reason } });
      setVoiding(null);
      setReason("");
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <ul className="move-history">
      {moves.map((m) => (
        <li key={m.id} className={m.voided ? "is-removed" : ""}>
          <span className={`flag ${m.kind === "to_job" ? "flag-info" : "flag-warn"}`}>{m.kind === "to_job" ? "Sent" : "Back"}</span>
          <span className="mh-what">
            <b>{fmt(m.quantity)} {m.unit}</b> {m.description}
            {m.lot_number && <span className="sub-inline"> · lot {m.lot_number}</span>}
            <span className="sub">
              {m.recorded_by}, {timeLabel(m.recorded_at)}
              {m.note && ` · ${m.note}`}
              {m.voided && ` · Voided: ${m.void_reason}`}
            </span>
          </span>
          {canVoid && !m.voided && (
            <button className="link" onClick={() => { setVoiding(voiding === m.id ? null : m.id); setError(null); }}>Void</button>
          )}
          {voiding === m.id && (
            <form className="void-form" onSubmit={doVoid}>
              <label>
                Reason
                <input required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Logged twice" autoFocus />
              </label>
              <button className="btn-danger">Void entry</button>
              {error && <p className="alert" role="alert">{error}</p>}
            </form>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function JobMaterials({ jobId, me, compact = false, onChanged }) {
  const cacheKey = `cf.mats.${jobId}`;
  const [data, setData] = useState(() => safeGet(cacheKey));
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(null); // { kind, key? }
  const [showHistory, setShowHistory] = useState(false);
  const [version, setVersion] = useState(0);
  const [offline, setOffline] = useState(false);
  const canLog = me.manages_stock;
  const dollars = me.sees_dollars;

  const load = useCallback(async () => {
    try {
      const d = await api(`/api/jobs/${jobId}/materials`);
      setData(d);
      safeSet(cacheKey, d);
      setOffline(false);
    } catch (e) {
      if (e.status === 0) setOffline(true);
    }
  }, [jobId, cacheKey]);
  useEffect(() => void load(), [load, version]);
  useEffect(() => {
    if (canLog) api("/api/items").then(setItems).catch(() => {});
  }, [canLog, version]);

  const changed = () => {
    setOpen(null);
    setVersion((v) => v + 1);
    onChanged?.();
  };

  if (!data) return <p className="help">{offline ? "No signal. The material list loads once there's a connection." : "Loading materials…"}</p>;
  const rows = data.rows;
  const toggle = (kind, key) => setOpen((o) => (o?.kind === kind && o?.key === key ? null : { kind, key }));
  const cols = 6 + (dollars ? 2 : 0) + (canLog ? 1 : 0);

  return (
    <div className={`job-mats ${compact ? "compact" : ""}`}>
      {offline && <p className="help">No signal. Showing the list from the last time it loaded.</p>}
      {!rows.length ? (
        <p className="help">No materials on this job's estimate yet.{canLog ? " You can still log anything sent to it." : ""}</p>
      ) : (
        <div className="table-scroll">
          <table className="mats-table">
            <thead>
              <tr>
                <th scope="col">Material</th>
                <th scope="col" className="num">Planned</th>
                <th scope="col" className="num">Sent</th>
                <th scope="col" className="num">Back</th>
                <th scope="col" className="num">Used</th>
                <th scope="col">Status</th>
                {dollars && <th scope="col" className="num">Est. cost</th>}
                {dollars && <th scope="col" className="num">Actual</th>}
                {canLog && <th scope="col"><span className="sr-only">Log</span></th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const [label, tone] = r.on_estimate ? STATUS[r.status] : ["Not on estimate", "s-off"];
                const out = r.sent - r.returned;
                return (
                  <Fragment key={r.key}>
                    <tr>
                      <th scope="row">
                        {r.description}
                        <span className="sub">
                          {r.unit}
                          {r.lots.length > 0 && ` · lot ${r.lots.join(", ")}`}
                          {r.on_hand != null && canLog && ` · ${fmt(r.on_hand)} on hand`}
                        </span>
                      </th>
                      <td className="num">{r.on_estimate ? fmt(r.planned) : "—"}</td>
                      <td className="num">{fmt(r.sent)}</td>
                      <td className="num">{r.returned ? fmt(r.returned) : ""}</td>
                      <td className={`num ${r.on_estimate && r.used_vs_planned > 0 ? "t-over" : ""}`}>{fmt(r.used)}</td>
                      <td>
                        <span className={`signin-status ${tone}`}>{label}</span>
                        {r.status === "partly_sent" && <span className="sub">{fmt(r.left_to_send)} left to send</span>}
                      </td>
                      {dollars && <td className="num">{r.on_estimate ? money(r.estimated_cost) : ""}</td>}
                      {dollars && <td className="num">{money(r.actual_cost)}</td>}
                      {canLog && (
                        <td className="row-actions">
                          <button className="link" onClick={() => toggle("to_job", r.key)}>Send</button>
                          {out > 0 && <button className="link" onClick={() => toggle("from_job", r.key)}>Return</button>}
                        </td>
                      )}
                    </tr>
                    {open?.key === r.key && (
                      <tr className="row-open">
                        <td colSpan={cols}>
                          <MoveForm jobId={jobId} row={r} kind={open.kind} items={items} onDone={changed} onCancel={() => setOpen(null)} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
            {dollars && data.summary.estimated_cost != null && (
              <tfoot>
                <tr>
                  <th scope="row">Materials</th>
                  <td colSpan={5} />
                  <td className="num">{money(data.summary.estimated_cost)}</td>
                  <td className={`num ${data.summary.actual_cost > data.summary.estimated_cost ? "t-over" : ""}`}>{money(data.summary.actual_cost)}</td>
                  {canLog && <td />}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
      {canLog && (
        <div className="add-row">
          <button className="btn-ghost" onClick={() => toggle("to_job", "__extra")}>Send something not on the list</button>
          <button className="btn-ghost" onClick={() => setShowHistory((s) => !s)}>{showHistory ? "Hide history" : "Show history"}</button>
        </div>
      )}
      {!canLog && rows.length > 0 && (
        <div className="add-row">
          <button className="btn-ghost" onClick={() => setShowHistory((s) => !s)}>{showHistory ? "Hide history" : "What went out and when"}</button>
        </div>
      )}
      {open?.key === "__extra" && (
        <MoveForm jobId={jobId} row={null} kind="to_job" items={items} onDone={changed} onCancel={() => setOpen(null)} />
      )}
      {showHistory && <History jobId={jobId} canVoid={canLog} version={version} onChanged={changed} />}
      <p className="help">
        Used = sent minus brought back. {canLog ? "Log returns when the crew brings leftovers back so the warehouse count stays right." : ""}
      </p>
    </div>
  );
}
