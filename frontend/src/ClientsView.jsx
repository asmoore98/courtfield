// Clients: everyone the work is for, with their leads, estimates and jobs.
import { useEffect, useState } from "react";
import { api } from "./api";
import { blankClient } from "./ClientPicker";
import { ActivityList, LEAD_STATUS, LinkList, LinksField, NoteAction, Restored, StatusChip, money0, useApi, useDraft, useScreen } from "./bits";

const SCREEN_KEY = "cf.clients.screen";
const JOB_STATUS = { scheduled: "Scheduled", active: "In progress", complete: "Complete" };

export default function ClientsView({ me, go, initial }) {
  const [screen, setScreen] = useScreen(SCREEN_KEY, initial);
  const open = (id) => setScreen({ view: "client", id });
  const toList = () => setScreen({ view: "list" });
  if (screen.view === "edit")
    return <ClientForm clientId={screen.id} onDone={open} onCancel={() => (screen.id ? open(screen.id) : toList())} />;
  if (screen.view === "client")
    return <ClientDetail me={me} id={screen.id} go={go} onBack={toList} onEdit={() => setScreen({ view: "edit", id: screen.id })} />;
  return <ClientList me={me} onOpen={open} onNew={() => setScreen({ view: "edit" })} />;
}

function ClientList({ me, onOpen, onNew }) {
  const [showOff, setShowOff] = useState(false);
  const { data, error } = useApi(`/api/clients${showOff ? "?include_inactive=true" : ""}`);
  const [q, setQ] = useState("");
  if (error && !data) return <p className="empty">Couldn't load clients: {error}</p>;
  if (!data) return <p className="empty">Loading clients…</p>;
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = data.filter((c) => {
    const hay = `${c.name} ${c.contact_name} ${c.phone} ${c.email}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
  return (
    <div className="sales">
      <div className="list-head spread">
        <h2 className="detail-title">Clients</h2>
        <button className="btn" onClick={onNew}>
          New client
        </button>
      </div>
      <div className="filter-row">
        <input className="search" type="search" placeholder="Search name, contact, phone…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search clients" />
        {me.role === "gm" && (
          <label className="check">
            <input type="checkbox" checked={showOff} onChange={(e) => setShowOff(e.target.checked)} /> Show turned-off clients
          </label>
        )}
      </div>
      {!shown.length ? (
        <p className="empty">{data.length ? "No client matches that." : "No clients yet. They're added here, or from a new lead or estimate."}</p>
      ) : (
        <ul className="row-list boxed">
          {shown.map((c) => (
            <li key={c.id}>
              <button className="row-btn" onClick={() => onOpen(c.id)}>
                <span className="row-main">
                  <b>{c.name}</b>
                  {!c.active && <span className="chip">Off</span>}
                  <span className="sub">{[c.contact_name, c.phone].filter(Boolean).join(" · ") || "No contact yet"}</span>
                </span>
                <span className="row-side sub">
                  {[c.leads && `${c.leads} lead${c.leads > 1 ? "s" : ""}`, c.estimates && `${c.estimates} estimate${c.estimates > 1 ? "s" : ""}`, c.jobs && `${c.jobs} job${c.jobs > 1 ? "s" : ""}`]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ClientDetail({ me, id, go, onBack, onEdit }) {
  const { data: c, error, reload } = useApi(`/api/clients/${id}`);
  if (error && !c) return <p className="empty">Couldn't load the client: {error}</p>;
  if (!c) return <p className="empty">Loading client…</p>;
  return (
    <div className="detail sales">
      <button className="link back" onClick={onBack}>
        All clients
      </button>
      <div className="detail-head">
        <div>
          <p className="eyebrow">Client{!c.active && " · turned off"}</p>
          <h2 className="detail-title">{c.name}</h2>
        </div>
        <div className="detail-actions">
          <button className="btn-ghost" onClick={onEdit}>
            Edit client
          </button>
          <button className="btn-ghost" onClick={() => go("leads", { view: "edit", clientId: id })}>
            New lead
          </button>
          {me.role === "gm" && (
            <NoteAction
              label={c.active ? "Turn off" : "Turn back on"}
              tone={c.active ? "danger" : undefined}
              prompt={c.active ? "Why? (duplicate, out of business…) They stay on record." : "Why turn them back on?"}
              onSubmit={(n) => api(`/api/clients/${id}/active`, { method: "PATCH", body: { active: !c.active, reason: n } }).then(reload)}
            />
          )}
        </div>
      </div>

      <section className="panel">
        <h3>Contact</h3>
        <dl className="facts">
          <div>
            <dt>Contact</dt>
            <dd>{c.contact_name || "—"}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>{c.phone ? <a href={`tel:${c.phone}`}>{c.phone}</a> : "—"}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{c.email ? <a href={`mailto:${c.email}`}>{c.email}</a> : "—"}</dd>
          </div>
          <div>
            <dt>Billing address</dt>
            <dd>{c.billing_address || "—"}</dd>
          </div>
        </dl>
        {c.notes && <p className="pre">{c.notes}</p>}
        <h4>Plans &amp; documents</h4>
        <LinkList text={c.links} empty="No links yet." />
      </section>

      <section className="panel">
        <h3>Estimates</h3>
        {!c.estimates.length ? (
          <p className="help">None yet.</p>
        ) : (
          <ul className="row-list">
            {c.estimates.map((e) => (
              <li key={e.id}>
                <button className="row-btn" onClick={() => go("estimates", { view: "detail", id: e.id })}>
                  <span className="row-main">
                    <b>{e.name}</b>
                    <span className="sub">
                      {e.number} · v{e.version}
                    </span>
                  </span>
                  <span className="row-side">
                    <StatusChip status={e.status} />
                    <span className="sub">{money0(e.price)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {c.leads.length > 0 && (
        <section className="panel">
          <h3>Leads</h3>
          <ul className="row-list">
            {c.leads.map((l) => (
              <li key={l.id}>
                <button className="row-btn" onClick={() => go("leads", { view: "lead", id: l.id })}>
                  <span className="row-main">
                    <b>{l.name}</b>
                  </span>
                  <span className="row-side">
                    <StatusChip status={l.status} label={LEAD_STATUS[l.status]} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {me.estimates && (
        <section className="panel">
          <h3>Jobs</h3>
          {!c.jobs.length ? (
            <p className="help">None yet. Jobs show up here when a won estimate becomes a job.</p>
          ) : (
            <ul className="row-list">
              {c.jobs.map((j) => (
                <li key={j.id}>
                  <button className="row-btn" onClick={() => go("office", { view: "job", id: j.id })}>
                    <span className="row-main">
                      <b>{j.name}</b>
                    </span>
                    <span className="row-side">
                      <span className="chip">{JOB_STATUS[j.status]}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <ActivityList items={c.activity} />
    </div>
  );
}

const blankForm = () => ({ ...blankClient(), notes: "", links: "" });

function ClientForm({ clientId, onDone, onCancel }) {
  const d = useDraft(`cf.draft.client.${clientId ?? "new"}`, blankForm());
  const [loaded, setLoaded] = useState(!clientId || !!d.restoredAt);
  const [fetchN, setFetchN] = useState(0);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const f = d.form;

  useEffect(() => {
    if (!clientId || d.restoredAt) return;
    api(`/api/clients/${clientId}`)
      .then((c) => {
        d.discard({ ...blankForm(), ...Object.fromEntries(Object.keys(blankForm()).map((k) => [k, c[k] ?? ""])) });
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, [clientId, fetchN]);

  if (!loaded) return <p className="empty">{error ?? "Loading client…"}</p>;

  async function save(e) {
    e.preventDefault();
    setError(null);
    if (!f.name.trim()) return setError("Give the client a name.");
    setSaving(true);
    try {
      const body = { ...f, name: f.name.trim() };
      const saved = clientId ? await api(`/api/clients/${clientId}`, { method: "PUT", body }) : await api("/api/clients", { method: "POST", body });
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
        {clientId ? "Back to client" : "All clients"}
      </button>
      <h2 className="detail-title">{clientId ? "Edit client" : "New client"}</h2>
      <Restored
        at={d.restoredAt}
        label={clientId ? "Throw it away" : "Start over"}
        onDiscard={() => {
          d.discard(blankForm());
          if (clientId) {
            setLoaded(false);
            setFetchN((n) => n + 1);
          }
        }}
      />
      <section className="panel">
        <div className="grid">
          <label className="span-2">
            Client or company name
            <input value={f.name} onChange={(e) => d.set("name", e.target.value)} required />
          </label>
          <label>
            Contact person
            <input value={f.contact_name} onChange={(e) => d.set("contact_name", e.target.value)} />
          </label>
          <label>
            Phone
            <input type="tel" value={f.phone} onChange={(e) => d.set("phone", e.target.value)} />
          </label>
          <label className="span-2">
            Email
            <input type="email" value={f.email} onChange={(e) => d.set("email", e.target.value)} autoCapitalize="none" />
          </label>
          <label className="span-2">
            Billing address
            <input value={f.billing_address} onChange={(e) => d.set("billing_address", e.target.value)} />
          </label>
          <label className="span-2">
            Notes
            <textarea rows={3} value={f.notes} onChange={(e) => d.set("notes", e.target.value)} />
          </label>
          <div className="span-2">
            <LinksField id="client-links" value={f.links} onChange={(v) => d.set("links", v)} />
          </div>
        </div>
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
          {saving ? "Saving…" : clientId ? "Save changes" : "Save client"}
        </button>
      </div>
    </form>
  );
}
