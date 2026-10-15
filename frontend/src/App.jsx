import { useEffect, useState } from "react";
import { api, clearToken, getToken, safeGet, safeSet, setToken } from "./api";
import FieldView from "./FieldView";
import OfficeView from "./OfficeView";

const ME_KEY = "cf.me";
const DEV_ACCOUNTS = [
  ["dev-lead-1", "Crew lead"],
  ["dev-gm", "General manager"],
  ["dev-owner", "Owner"],
  ["dev-estimator", "Estimator"],
];

function SignIn({ onSignedIn }) {
  const [token, setTok] = useState("");
  const [error, setError] = useState(null);

  async function go(t) {
    setError(null);
    setToken(t);
    try {
      onSignedIn(await api("/api/me"));
    } catch (e) {
      clearToken();
      setError(e.status === 401 ? "That access code isn't recognized." : `Couldn't reach the server: ${e.message}`);
    }
  }

  return (
    <main className="signin">
      <h1 className="wordmark">Courtfield</h1>
      <p className="signin-lede">Crew hours by task, measured against the estimate.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (token.trim()) go(token.trim());
        }}
      >
        <label htmlFor="tok">Access code</label>
        <div className="signin-row">
          <input id="tok" value={token} onChange={(e) => setTok(e.target.value)} autoComplete="off" autoCapitalize="none" />
          <button className="btn" type="submit">
            Sign in
          </button>
        </div>
        {error && <p className="err">{error}</p>}
      </form>
      <div className="devpick">
        <p>Sample accounts (development only)</p>
        {DEV_ACCOUNTS.map(([t, label]) => (
          <button key={t} className="btn-ghost" onClick={() => go(t)}>
            {label}
          </button>
        ))}
      </div>
    </main>
  );
}

export default function App() {
  const [me, setMe] = useState(() => (getToken() ? safeGet(ME_KEY) : null));
  const [mode, setMode] = useState(null);

  useEffect(() => {
    if (!getToken()) return;
    api("/api/me")
      .then((m) => {
        setMe(m);
        safeSet(ME_KEY, m);
      })
      .catch((e) => {
        if (e.status === 401) signOut();
      });
  }, []);

  function signOut() {
    clearToken();
    safeSet(ME_KEY, null);
    setMe(null);
    setMode(null);
  }

  if (!me) return <SignIn onSignedIn={(m) => (safeSet(ME_KEY, m), setMe(m))} />;

  const canField = me.enters_time;
  const canOffice = me.sees_dollars;
  const view = mode ?? (canOffice ? "office" : "field");

  return (
    <div className="app">
      <header className="topbar">
        <span className="wordmark small">Courtfield</span>
        {canField && canOffice && (
          <nav className="switch" aria-label="View">
            <button aria-pressed={view === "field"} onClick={() => setMode("field")}>
              Field
            </button>
            <button aria-pressed={view === "office"} onClick={() => setMode("office")}>
              Office
            </button>
          </nav>
        )}
        <span className="who">
          {me.name}
          <button className="link" onClick={signOut}>
            Sign out
          </button>
        </span>
      </header>
      <main className="content">
        {!canField && !canOffice ? (
          <p className="empty">Your role doesn't have a screen yet. Materials and warehouse tools arrive in Phase 2.</p>
        ) : view === "field" && canField ? (
          <FieldView />
        ) : (
          <OfficeView />
        )}
      </main>
    </div>
  );
}
