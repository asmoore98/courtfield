// Materials tab: the price list (estimators and GM set prices), warehouse
// stock on hand (receive deliveries, correct counts), and each open job's
// material list for the warehouse to load out and check back in.
import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { COST_CATEGORIES } from "./JobEditor";
import JobMaterials from "./JobMaterials";

const CAT = { ...Object.fromEntries(COST_CATEGORIES), equipment: "Rental", subcontractor: "Sub" };
const fmt = (n) => (Math.round(n * 100) / 100).toLocaleString("en-US", { maximumFractionDigits: 2 });
const money2 = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
const UNITS = ["pail", "gal", "drum", "bag", "lb", "ton", "SF", "LF", "roll", "each", "set", "day", "hr", "job"];

function ItemForm({ item, onSaved, onCancel }) {
  const [f, setF] = useState(() => ({
    name: item?.name ?? "",
    category: item?.category ?? "material",
    unit: item?.unit ?? "pail",
    unit_cost: item?.unit_cost ?? "",
    sku: item?.sku ?? "",
    track_stock: item?.track_stock ?? true,
  }));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const id = (k) => `if-${item?.id ?? "new"}-${k}`;

  async function save(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const body = { ...f, name: f.name.trim(), unit: f.unit.trim(), unit_cost: Number(f.unit_cost || 0) };
    try {
      await (item ? api(`/api/items/${item.id}`, { method: "PATCH", body }) : api("/api/items", { method: "POST", body }));
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="timeform" onSubmit={save}>
      <h4>{item ? `Edit ${item.name}` : "Add to the price list"}</h4>
      <div className="tf-grid">
        <label htmlFor={id("name")} className="tf-reason">
          Name
          <input id={id("name")} required value={f.name} onChange={set("name")} placeholder="e.g. Acrylic resurfacer, 5 gal" />
        </label>
        <label htmlFor={id("cat")}>
          Type
          <select id={id("cat")} value={f.category} onChange={set("category")}>
            {COST_CATEGORIES.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
        <label htmlFor={id("unit")}>
          Unit
          <input id={id("unit")} list="cf-item-units" value={f.unit} onChange={set("unit")} maxLength={20} />
        </label>
        <label htmlFor={id("cost")}>
          Cost per unit
          <span className="affix">
            <span aria-hidden="true">$</span>
            <input id={id("cost")} type="number" inputMode="decimal" min="0" step="0.01" value={f.unit_cost} onChange={set("unit_cost")} />
          </span>
        </label>
        <label htmlFor={id("sku")}>
          Supplier part number
          <input id={id("sku")} value={f.sku} onChange={set("sku")} maxLength={60} placeholder="Optional" />
        </label>
        <label className="check tf-reason" htmlFor={id("track")}>
          <input id={id("track")} type="checkbox" checked={f.track_stock} onChange={set("track_stock")} />
          The warehouse keeps this in stock (count it in and out)
        </label>
      </div>
      <datalist id="cf-item-units">
        {UNITS.map((u) => <option key={u} value={u} />)}
      </datalist>
      {item && <p className="help">Changing the cost updates new estimates. Jobs already estimated keep the price they were built with.</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="tf-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={busy}>{busy ? "Saving…" : item ? "Save" : "Add item"}</button>
      </div>
    </form>
  );
}

function StockForm({ item, kind, canSeeCost, onSaved, onCancel }) {
  const [qty, setQty] = useState("");
  const [cost, setCost] = useState(item.unit_cost ?? "");
  const [note, setNote] = useState("");
  const [counted, setCounted] = useState(""); // for counts: what's actually on the shelf
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setError(null);
    let quantity = Number(qty);
    if (kind === "adjust") {
      quantity = Math.round((Number(counted) - (item.on_hand ?? 0)) * 1000) / 1000;
      if (!quantity) return setError("That matches what the app shows. Nothing to correct.");
    }
    setBusy(true);
    const body = { kind, item_id: item.id, quantity, note };
    if (kind === "receive" && canSeeCost && cost !== "") body.unit_cost = Number(cost);
    try {
      await api("/api/stock/moves", { method: "POST", body });
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="timeform" onSubmit={save}>
      <h4>{kind === "receive" ? `Receive ${item.name}` : `Count ${item.name}`}</h4>
      <div className="tf-grid">
        {kind === "receive" ? (
          <>
            <label>
              Quantity received ({item.unit})
              <input type="number" inputMode="decimal" min="0" step="any" required value={qty} onChange={(e) => setQty(e.target.value)} />
            </label>
            {canSeeCost && (
              <label>
                Paid per unit
                <span className="affix">
                  <span aria-hidden="true">$</span>
                  <input type="number" inputMode="decimal" min="0" step="0.01" value={cost} onChange={(e) => setCost(e.target.value)} />
                </span>
              </label>
            )}
          </>
        ) : (
          <label>
            Counted on the shelf ({item.unit})
            <input type="number" inputMode="decimal" min="0" step="any" required value={counted} onChange={(e) => setCounted(e.target.value)} />
          </label>
        )}
        <label className="tf-reason">
          {kind === "receive" ? "Note (PO, supplier, delivery)" : "Reason for the difference"}
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} required={kind === "adjust"} />
        </label>
      </div>
      {kind === "adjust" && <p className="help">The app shows {fmt(item.on_hand ?? 0)} {item.unit}. Saving sets it to what you counted.</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="tf-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={busy}>{busy ? "Saving…" : kind === "receive" ? "Add to stock" : "Save count"}</button>
      </div>
    </form>
  );
}

function ItemHistory({ item }) {
  const [moves, setMoves] = useState(null);
  useEffect(() => {
    api(`/api/stock/moves?item_id=${item.id}&limit=50`).then(setMoves).catch(() => setMoves([]));
  }, [item.id]);
  const WORD = { receive: "Received", to_job: "Sent to", from_job: "Back from", adjust: "Count correction" };
  if (!moves) return <p className="help">Loading…</p>;
  if (!moves.length) return <p className="help">No movement yet.</p>;
  return (
    <ul className="move-history">
      {moves.map((m) => (
        <li key={m.id} className={m.voided ? "is-removed" : ""}>
          <span className="mh-what">
            <b>{m.kind === "to_job" ? "−" : m.quantity < 0 ? "" : "+"}{fmt(m.quantity)} {m.unit}</b> {WORD[m.kind]} {m.job_name ?? ""}
            <span className="sub">
              {m.recorded_by}, {new Date(m.recorded_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              {m.lot_number && ` · lot ${m.lot_number}`}
              {m.note && ` · ${m.note}`}
              {m.voided && ` · Voided: ${m.void_reason}`}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function PriceList({ me, refresh = 0 }) {
  const [items, setItems] = useState(null);
  const [showInactive, setShowInactive] = useState(false);
  const [open, setOpen] = useState(null); // { kind: "add"|"edit"|"receive"|"adjust"|"history", id? }
  const [filter, setFilter] = useState("");
  const load = useCallback(
    () => api(`/api/items${showInactive ? "?include_inactive=true" : ""}`).then(setItems).catch(() => setItems([])),
    [showInactive, refresh] // eslint-disable-line react-hooks/exhaustive-deps
  );
  useEffect(() => void load(), [load]);
  const done = () => {
    setOpen(null);
    load();
  };
  const toggle = (kind, id) => setOpen((o) => (o?.kind === kind && o?.id === id ? null : { kind, id }));
  const canEdit = me.edits_prices;
  const canStock = me.manages_stock;
  const seesCost = me.sees_dollars;

  async function setActive(item, active) {
    await api(`/api/items/${item.id}`, { method: "PATCH", body: { active } });
    load();
  }

  if (!items) return <p className="empty">Loading the price list…</p>;
  const shown = items.filter((i) => !filter || i.name.toLowerCase().includes(filter.toLowerCase()));
  const cols = 3 + (seesCost ? 1 : 0) + 1;

  return (
    <section className="panel">
      <div className="panel-head">
        <h3>{canEdit ? "Price list and stock" : "Stock"}</h3>
        <div className="log-tools">
          <input className="search" type="search" placeholder="Find an item" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Find an item" />
          {canEdit && <button className="btn" onClick={() => toggle("add")}>Add item</button>}
        </div>
      </div>
      {open?.kind === "add" && <ItemForm onSaved={done} onCancel={() => setOpen(null)} />}
      {!items.length ? (
        <p className="empty">
          {canEdit
            ? "No items yet. Add the coatings, sand, line paint, nets and other things you buy, with what you pay. Estimates then pick from this list."
            : "No items on the price list yet. The GM or estimator adds them."}
        </p>
      ) : (
        <div className="table-scroll">
          <table className="items-table">
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Unit</th>
                {seesCost && <th scope="col" className="num">Cost per unit</th>}
                <th scope="col" className="num">On hand</th>
                <th scope="col"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {shown.map((i) => (
                <Fragment key={i.id}>
                  <tr className={i.active ? "" : "is-removed"}>
                    <th scope="row">
                      {i.name}
                      <span className="sub">{CAT[i.category]}{i.sku ? ` · ${i.sku}` : ""}{!i.active ? " · Not in use" : ""}</span>
                    </th>
                    <td>{i.unit}</td>
                    {seesCost && <td className="num">{money2(i.unit_cost)}</td>}
                    <td className={`num ${i.on_hand != null && i.on_hand < 0 ? "t-over" : ""}`}>
                      {i.on_hand == null ? <span className="sub-inline">Not stocked</span> : fmt(i.on_hand)}
                    </td>
                    <td className="row-actions">
                      {canStock && i.track_stock && i.active && (
                        <>
                          <button className="link" onClick={() => toggle("receive", i.id)}>Receive</button>
                          <button className="link" onClick={() => toggle("adjust", i.id)}>Count</button>
                        </>
                      )}
                      {i.track_stock && <button className="link" onClick={() => toggle("history", i.id)}>History</button>}
                      {canEdit && <button className="link" onClick={() => toggle("edit", i.id)}>Edit</button>}
                      {canEdit && (i.active
                        ? <button className="link danger" onClick={() => setActive(i, false)}>Stop using</button>
                        : <button className="link" onClick={() => setActive(i, true)}>Use again</button>)}
                    </td>
                  </tr>
                  {open?.id === i.id && (
                    <tr className="row-open">
                      <td colSpan={cols}>
                        {open.kind === "edit" && <ItemForm item={i} onSaved={done} onCancel={() => setOpen(null)} />}
                        {(open.kind === "receive" || open.kind === "adjust") && (
                          <StockForm item={i} kind={open.kind} canSeeCost={seesCost} onSaved={done} onCancel={() => setOpen(null)} />
                        )}
                        {open.kind === "history" && <ItemHistory item={i} />}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {canEdit && (
        <label className="check">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Show items no longer in use
        </label>
      )}
    </section>
  );
}

function JobLists({ me, onChanged }) {
  const [jobs, setJobs] = useState(null);
  const [openJob, setOpenJob] = useState(null);
  useEffect(() => {
    api("/api/jobs").then((js) => setJobs(js.filter((j) => j.status !== "complete"))).catch(() => setJobs([]));
  }, []);
  if (!jobs) return null;
  return (
    <section className="panel">
      <h3>Job material lists</h3>
      {!jobs.length ? (
        <p className="empty">No scheduled or active jobs.</p>
      ) : (
        <ul className="joblist">
          {jobs.map((j) => (
            <li key={j.id}>
              <button className={`jobrow ${openJob === j.id ? "is-open" : ""}`} onClick={() => setOpenJob(openJob === j.id ? null : j.id)} aria-expanded={openJob === j.id}>
                <span className="jobrow-head">
                  <span className="jobrow-name">{j.name}</span>
                  <span className={`chip chip-${j.status}`}>{j.status === "active" ? "In progress" : "Scheduled"}</span>
                </span>
              </button>
              {openJob === j.id && (
                <div className="job-mats-wrap">
                  <JobMaterials jobId={j.id} me={me} onChanged={onChanged} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function MaterialsView({ me }) {
  const [refresh, setRefresh] = useState(0);
  return (
    <div className="materials">
      <h2 className="detail-title">Materials</h2>
      {me.manages_stock && <JobLists me={me} onChanged={() => setRefresh((n) => n + 1)} />}
      <PriceList me={me} refresh={refresh} />
    </div>
  );
}
