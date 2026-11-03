// Pick a returning client, or choose "New client" to fill in their details.
// The new client is created when the lead or estimate is saved (saveClient).
import { useEffect, useState } from "react";
import { api } from "./api";
import { AddressFields, addressBody, blankAddress } from "./bits";

export const blankClient = () => ({ name: "", contact_name: "", phone: "", email: "", billing_address: "", billing: blankAddress() });

export function ClientPicker({ clientId, newClient, onChange, id = "client-pick" }) {
  const [clients, setClients] = useState(null);
  useEffect(() => {
    api("/api/clients").then(setClients).catch(() => setClients([]));
  }, []);
  const isNew = clientId === "__new";
  const nc = newClient ?? blankClient();
  const setNc = (k, v) => onChange(clientId, { ...nc, [k]: v });

  return (
    <div className="client-pick">
      <label htmlFor={id}>
        Client
        <select id={id} value={clientId ?? ""} onChange={(e) => onChange(e.target.value, e.target.value === "__new" ? nc : null)}>
          <option value="">{clients ? "Choose a returning client…" : "Loading clients…"}</option>
          <option value="__new">+ New client</option>
          {(clients ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {isNew && (
        <fieldset className="new-client">
          <legend>New client</legend>
          <div className="grid">
            <label className="span-2">
              Client or company name
              <input value={nc.name} onChange={(e) => setNc("name", e.target.value)} placeholder="e.g. Harbor Pointe HOA" />
            </label>
            <label>
              Contact person
              <input value={nc.contact_name} onChange={(e) => setNc("contact_name", e.target.value)} />
            </label>
            <label>
              Phone
              <input type="tel" value={nc.phone} onChange={(e) => setNc("phone", e.target.value)} />
            </label>
            <label className="span-2">
              Email
              <input type="email" value={nc.email} onChange={(e) => setNc("email", e.target.value)} autoCapitalize="none" />
            </label>
            <div className="span-2">
              <AddressFields section="billing" legend="Billing address" value={nc.billing} onChange={(v) => setNc("billing", v)} />
            </div>
          </div>
        </fieldset>
      )}
    </div>
  );
}

// Before saving a lead or estimate: check the client choice and, for a new
// client, create it. Returns the client id.
export async function saveClient(clientId, newClient) {
  if (!clientId) throw Object.assign(new Error("Choose a client, or pick “+ New client”."), { field: "client" });
  if (clientId !== "__new") return clientId;
  const name = newClient?.name?.trim();
  if (!name) throw Object.assign(new Error("Give the new client a name."), { field: "client" });
  // A save that failed after the client was added (no signal, say) shouldn't add them twice.
  const existing = (await api("/api/clients")).find((c) => c.name.toLowerCase() === name.toLowerCase());
  if (existing) return existing.id;
  const { billing, ...rest } = newClient;
  const c = await api("/api/clients", { method: "POST", body: { ...rest, name, ...(billing ? addressBody(billing, "billing", "billing_address") : {}) } });
  return c.id;
}
