// Leads: what sales brings in for an estimator to price.
import { useEffect, useState } from "react";
import { api } from "./api";
import { ClientPicker, saveClient } from "./ClientPicker";
import { COURT_TYPES, SCOPE_TYPES } from "./JobEditor";
import {
  ActivityList, COURT_LABEL, LEAD_STATUS, LinkList, LinksField, NoteAction, Restored, SCOPE_LABEL, StatusChip, fmtDate, money0, useApi, useDraft, useScreen,
} from "./bits";

const SCREEN_KEY = "cf.leads.screen";

export default function LeadsView({ me, go, initial }) {
  const [screen, setScreen] = useScreen(SCREEN_KEY, initial);
  const toList = () => setScreen({ view: "list" });
  const open = (id) => setScreen({ view: "lead", id });

  if (screen.view === "edit")
    return <LeadForm me={me} leadId={screen.id} clientId={screen.clientId} onDone={open} onCancel={() => (screen.id ? open(screen.id) : toList())} />;
  if (screen.view === "lead")
    return <LeadDetail me={me} id={screen.id} go={go} onBack={toList} onEdit={() => setScreen({ view: "edit", id: screen.id })} />;
  return <LeadList me={me} onOpen={open} onNew={() => setScreen({ view: "edit" })} />;
}

function LeadList({ me, onOpen, onNew }) {
  const { data, error } = useApi("/api/leads");
  const [filter, setFilter] = useState("open");
  if (error && !data) return <p className="empty">Couldn't load leads: {error}</p>;
  if (!data) return <p className="empty">Loading leads…</p>;
  const groups = {
    open: (l) => ["new", "estimating"].includes(l.outcome),
    estimated: (l) => ["estimated", "expired"].includes(l.outcome),
    won: (l) => l.outcome === "won",
    lost: (l) => ["lost", "no_bid", "dropped"].includes(l.outcome),
    all: () => true,
  };
  const filters = [
    ["open", "Open"],
    ["estimated", "Estimate sent"],
    ["won", "Won"],
    ["lost", "Lost / dropped"],
    ["all", "All"],
  ];
  const shown = data.filter(groups[filter]);
  const waiting = data.filter((l) => l.status === "new").length;

  return (
    <div className="sales">
      <div className="list-head spread">
        <h2 className="detail-title">Leads</h2>
        <button className="btn" onClick={onNew}>
          New lead
        </button>
      </div>
      {me.estimates && waiting > 0 && (
        <p className="follow-note">
          <b>{waiting === 1 ? "1 lead is" : `${waiting} leads are`} waiting on an estimate.</b>
        </p>
      )}
      <div className="filter-row" role="group" aria-label="Show leads">
        {filters.map(([k, l]) => (
          <button key={k} className="filter" aria-pressed={filter === k} onClick={() => setFilter(k)}>
            {l} <span className="count">{data.filter(groups[k]).length}</span>
          </button>
        ))}
      </div>
      {!shown.length ? (
        <p className="empty">{data.length ? "Nothing here." : "No leads yet. Add one with New lead."}</p>
      ) : (
        <ul className="joblist">
          {shown.map((l) => (
            <li key={l.id}>
              <button className="jobrow" onClick={() => onOpen(l.id)}>
                <span className="jobrow-head">
                  <span className="jobrow-name">{l.name}</span>
                  <StatusChip status={l.outcome} label={LEAD_STATUS[l.outcome]} />
                </span>
                <span className="jobrow-foot">
                  <span>{l.client_name}</span>
                  {l.court_type && <span>{COURT_LABEL[l.court_type]}{l.scope_type && `, ${SCOPE_LABEL[l.scope_type].toLowerCase()}`}</span>}
                  {l.salesperson && <span>Sales: {l.salesperson}</span>}
                  {l.bid_due && <span className={new Date(l.bid_due) < new Date() && l.status === "new" ? "t-over" : ""}>Bid due {fmtDate(l.bid_due + "T12:00:00")}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LeadDetail({ me, id, go, onBack, onEdit }) {
  const { data: l, error, reload } = useApi(`/api/leads/${id}`);
  if (error && !l) return <p className="empty">Couldn't load the lead: {error}</p>;
  if (!l) return <p className="empty">Loading lead…</p>;
  const setStatus = (status, reason) => api(`/api/leads/${id}/status`, { method: "POST", body: { status, reason } }).then(reload);

  return (
    <div className="detail sales">
      <button className="link back" onClick={onBack}>
        All leads
      </button>
      <div className="detail-head">
        <div>
          <p className="eyebrow">
            Lead · <StatusChip status={l.outcome} label={LEAD_STATUS[l.outcome]} />
          </p>
          <h2 className="detail-title">{l.name}</h2>
          <p className="detail-sub">
            <button className="link" onClick={() => go("clients", { view: "client", id: l.client_id })}>
              {l.client_name}
            </button>
            {l.salesperson && ` · Sales: ${l.salesperson}`}
            {l.bid_due && ` · Bid due ${fmtDate(l.bid_due + "T12:00:00")}`}
          </p>
        </div>
      </div>

      <section className="panel">
        <h3>What's next</h3>
        <div className="action-row">
          {me.estimates && l.status !== "dropped" && l.outcome !== "won" && (
            <button className="btn" onClick={() => go("estimates", { view: "edit", leadId: l.id })}>
              {l.estimates.length ? "Start another estimate" : "Start the estimate"}
            </button>
          )}
          <button className="btn-ghost" onClick={onEdit}>
            Edit lead
          </button>
          {l.status !== "dropped" ? (
            <NoteAction label="Drop lead" tone="danger" prompt="Why are we dropping it?" onSubmit={(n) => setStatus("dropped", n)} />
          ) : (
            <NoteAction label="Reopen lead" prompt="Why reopen it?" onSubmit={(n) => setStatus("new", n)} />
          )}
        </div>
        {l.status === "dropped" && l.status_reason && <p className="help">Dropped: {l.status_reason}</p>}
      </section>

      <section className="panel">
        <h3>Details</h3>
        <dl className="facts">
          <div>
            <dt>Site</dt>
            <dd>
              {l.site_address || "No address yet"}
              {l.parcel_id && <span className="sub">Parcel {l.parcel_id}</span>}
            </dd>
          </div>
          <div>
            <dt>Work</dt>
            <dd>{l.court_type ? `${COURT_LABEL[l.court_type]}${l.scope_type ? `, ${SCOPE_LABEL[l.scope_type].toLowerCase()}` : ""}` : "Not set"}</dd>
          </div>
        </dl>
        {l.description ? <p className="pre">{l.description}</p> : <p className="help">No description yet.</p>}
        <h4>Plans &amp; documents</h4>
        <LinkList text={l.links} empty="No links yet. Edit the lead to paste Google Drive links." />
      </section>

      {l.estimates.length > 0 && (
        <section className="panel">
          <h3>Estimates</h3>
          <ul className="row-list">
            {l.estimates.map((e) => (
              <li key={e.id}>
                <button className="row-btn" onClick={() => go("estimates", { view: "detail", id: e.id })}>
                  <span className="row-main">
                    <b>{e.number}</b> · v{e.version}
                    <span className="sub">{e.name}</span>
                  </span>
                  <span className="row-side">
                    <StatusChip status={e.status} />
                    <span className="sub">{money0(e.price)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ActivityList items={l.activity} />
    </div>
  );
}

const blankLead = () => ({
  client_id: "",
  new_client: null,
  name: "",
  site_address: "",
  parcel_id: "",
  court_type: "",
  scope_type: "",
  description: "",
  links: "",
  bid_due: "",
  salesperson_id: "",
});

function LeadForm({ me, leadId, clientId, onDone, onCancel }) {
  const d = useDraft(`cf.draft.lead.${leadId ?? "new"}`, { ...blankLead(), client_id: clientId ?? "" });
  const [people, setPeople] = useState([]);
  const [loaded, setLoaded] = useState(!leadId || !!d.restoredAt);
  const [fetchN, setFetchN] = useState(0);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const f = d.form;

  useEffect(() => {
    api("/api/estimates/people").then(setPeople).catch(() => {});
  }, []);
  useEffect(() => {
    if (!leadId || d.restoredAt) return;
    api(`/api/leads/${leadId}`)
      .then((l) => {
        d.discard({ ...blankLead(), ...l, court_type: l.court_type ?? "", scope_type: l.scope_type ?? "", bid_due: l.bid_due ?? "", salesperson_id: l.salesperson_id ?? "" });
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, [leadId, fetchN]);

  if (!loaded) return <p className="empty">{error ?? "Loading lead…"}</p>;

  async function save(e) {
    e.preventDefault();
    setError(null);
    if (!f.name.trim()) return setError("Give the lead a project name.");
    setSaving(true);
    try {
      const client_id = await saveClient(f.client_id, f.new_client);
      const body = {
        client_id,
        name: f.name.trim(),
        site_address: f.site_address.trim(),
        parcel_id: f.parcel_id.trim(),
        court_type: f.court_type || null,
        scope_type: f.scope_type || null,
        description: f.description,
        links: f.links,
        bid_due: f.bid_due || null,
        salesperson_id: f.salesperson_id || null,
      };
      const saved = leadId ? await api(`/api/leads/${leadId}`, { method: "PUT", body }) : await api("/api/leads", { method: "POST", body });
      d.done();
      onDone(saved.id);
    } catch (err) {
      setError(err.status === 0 ? "No connection. Your work is kept on this device; save again when you have signal." : err.message);
      setSaving(false);
    }
  }

  return (
    <form className="editor" onSubmit={save}>
      <button type="button" className="link back" onClick={onCancel}>
        {leadId ? "Back to lead" : "All leads"}
      </button>
      <h2 className="detail-title">{leadId ? "Edit lead" : "New lead"}</h2>
      <Restored at={d.restoredAt} label={leadId ? "Throw it away" : "Start over"} onDiscard={() => {
          d.discard(blankLead());
          if (leadId) {
            setLoaded(false);
            setFetchN((n) => n + 1);
          }
        }} />

      <section className="panel">
        <h3>Who</h3>
        <ClientPicker
          clientId={f.client_id}
          newClient={f.new_client}
          onChange={(cid, nc) => d.setForm({ ...f, client_id: cid, new_client: nc })}
        />
        {me.role !== "sales" && (
          <div className="grid extra-top">
            <label>
              Salesperson
              <select value={f.salesperson_id} onChange={(e) => d.set("salesperson_id", e.target.value)}>
                <option value="">None</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Details</h3>
        <div className="grid">
          <label className="span-2">
            Project name
            <input value={f.name} onChange={(e) => d.set("name", e.target.value)} placeholder="e.g. Harbor Pointe – 2 pickleball courts" required />
          </label>
          <label>
            Court type <span className="optional">(if known)</span>
            <select value={f.court_type} onChange={(e) => d.set("court_type", e.target.value)}>
              <option value="">Not sure yet</option>
              {COURT_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Scope <span className="optional">(if known)</span>
            <select value={f.scope_type} onChange={(e) => d.set("scope_type", e.target.value)}>
              <option value="">Not sure yet</option>
              {SCOPE_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="span-2">
            Description
            <span className="help field-help">Court count and sizes, what's there now, wants and must-haves, budget, timing, who decides.</span>
            <textarea rows={5} value={f.description} onChange={(e) => d.set("description", e.target.value)} />
          </label>
          <label>
            Bid due <span className="optional">(optional)</span>
            <input type="date" value={f.bid_due} onChange={(e) => d.set("bid_due", e.target.value)} />
          </label>
        </div>
      </section>

      <section className="panel">
        <h3>Where</h3>
        <div className="grid">
          <label className="span-2">
            Site address
            <input value={f.site_address} onChange={(e) => d.set("site_address", e.target.value)} placeholder="Street, city, ZIP" />
          </label>
          <label className="span-2">
            <span>
              Parcel ID <span className="optional">(optional)</span>
            </span>
            <input value={f.parcel_id} onChange={(e) => d.set("parcel_id", e.target.value)} maxLength={60} />
          </label>
        </div>
      </section>

      <section className="panel">
        <LinksField id="lead-links" value={f.links} onChange={(v) => d.set("links", v)} />
      </section>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="editor-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn" disabled={saving}>
          {saving ? "Saving…" : leadId ? "Save changes" : "Save lead"}
        </button>
      </div>
    </form>
  );
}
