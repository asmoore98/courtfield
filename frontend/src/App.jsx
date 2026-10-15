import { useEffect, useState } from "react";
import { DEMO, api, clearToken, getToken, onSignedOut, safeGet, safeSet, setToken } from "./api";
import FieldView from "./FieldView";
import OfficeView from "./OfficeView";
import TeamView from "./TeamView";
import TimesheetView from "./TimesheetView";
import MaterialsView from "./MaterialsView";

const ME_KEY = "cf.me";
// Sample sign-ins: shown in the preview and in local development only.
const SAMPLE_PASSWORD = "courtfield-dev";
const SAMPLE_ACCOUNTS = [
  ["lead-1@sample.test", "Crew lead"],
  ["gm@sample.test", "General manager"],
  ["owner@sample.test", "Owner"],
  ["estimator@sample.test", "Estimator"],
];
const SHOW_SAMPLES = DEMO || import.meta.env.DEV;

const deviceName = () => {
  const ua = navigator.userAgent;
  const os = /iphone/i.test(ua) ? "iPhone" : /ipad/i.test(ua) ? "iPad" : /android/i.test(ua) ? "Android" : /mac/i.test(ua) ? "Mac" : /windows/i.test(ua) ? "Windows" : "Browser";
  return `${os} · ${new Date().toLocaleDateString()}`;
};

function DemoBanner() {
  if (!DEMO) return null;
  async function reset() {
    const { resetDemo } = await import("./demoServer.js");
    resetDemo();
    location.reload();
  }
  return (
    <div className="demo-banner">
      <span>Preview with sample data. Changes are saved only in this browser.</span>
      <button className="link" onClick={reset}>
        Reset sample data
      </button>
    </div>
  );
}

function SignIn({ onSignedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function go(em, pw) {
    setError(null);
    setBusy(true);
    try {
      const { token, me } = await api("/api/auth/login", { method: "POST", body: { email: em, password: pw, device: deviceName() } });
      setToken(token);
      onSignedIn(me);
    } catch (e) {
      setError(e.status === 0 ? "No connection. Sign in once you have signal; after that the app works offline." : e.message);
      setBusy(false);
    }
  }

  return (
    <>
      <DemoBanner />
      <main className="signin">
        <h1 className="wordmark">Courtfield</h1>
        <p className="signin-lede">Crew hours by task, measured against the estimate.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            go(email.trim(), password);
          }}
        >
          <label htmlFor="si-email">Email</label>
          <input id="si-email" type="email" autoComplete="username" autoCapitalize="none" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <label htmlFor="si-pw">Password</label>
          <input id="si-pw" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className="btn wide" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          {error && <p className="err" role="alert">{error}</p>}
        </form>
        <p className="help">Forgot your password or never set one? Ask your manager for a new sign-in link.</p>
        {SHOW_SAMPLES && (
          <div className="devpick">
            <p>Sample accounts</p>
            {SAMPLE_ACCOUNTS.map(([em, label]) => (
              <button key={em} className="btn-ghost" disabled={busy} onClick={() => go(em, SAMPLE_PASSWORD)}>
                {label}
              </button>
            ))}
          </div>
        )}
      </main>
    </>
  );
}

function AcceptInvite({ token, onSignedIn }) {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api(`/api/auth/invite/${token}`)
      .then(setInfo)
      .catch((e) => setError(e.message));
  }, [token]);

  async function save(e) {
    e.preventDefault();
    setError(null);
    if (pw !== pw2) return setError("The two passwords don't match.");
    setBusy(true);
    try {
      const { token: session, me } = await api(`/api/auth/invite/${token}`, { method: "POST", body: { password: pw, device: deviceName() } });
      setToken(session);
      history.replaceState(null, "", "/");
      onSignedIn(me);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <>
      <DemoBanner />
      <main className="signin">
        <h1 className="wordmark">Courtfield</h1>
        {!info && !error && <p className="signin-lede">Checking your link…</p>}
        {!info && error && (
          <>
            <p className="signin-lede">{error}</p>
            <button className="btn-ghost" onClick={() => (history.replaceState(null, "", "/"), location.reload())}>
              Go to sign in
            </button>
          </>
        )}
        {info && (
          <form onSubmit={save}>
            <p className="signin-lede">
              {info.resetting ? `Set a new password, ${info.name.split(" ")[0]}.` : `Welcome, ${info.name.split(" ")[0]}. Set a password to start using Courtfield for ${info.company_name}.`}
            </p>
            {info.email && <p className="help">You'll sign in with {info.email}.</p>}
            <input type="email" autoComplete="username" value={info.email ?? ""} readOnly hidden />
            <label htmlFor="ai-pw">New password</label>
            <input id="ai-pw" type="password" autoComplete="new-password" minLength={8} required value={pw} onChange={(e) => setPw(e.target.value)} />
            <label htmlFor="ai-pw2">Type it again</label>
            <input id="ai-pw2" type="password" autoComplete="new-password" minLength={8} required value={pw2} onChange={(e) => setPw2(e.target.value)} />
            <p className="help">At least 8 characters.</p>
            <button className="btn wide" disabled={busy}>
              {busy ? "Saving…" : "Save password and sign in"}
            </button>
            {error && <p className="err" role="alert">{error}</p>}
          </form>
        )}
      </main>
    </>
  );
}

const inviteToken = () => location.pathname.match(/^\/invite\/([\w-]+)$/)?.[1] ?? (location.hash.match(/^#invite-([\w-]+)$/)?.[1] || null);

export default function App() {
  const [me, setMe] = useState(() => (getToken() ? safeGet(ME_KEY) : null));
  const [mode, setMode] = useState(null);
  const [invite, setInvite] = useState(inviteToken);

  function signedIn(m) {
    safeSet(ME_KEY, m);
    setInvite(null);
    setMode(null);
    setMe(m);
  }

  function signOut() {
    clearToken();
    safeSet(ME_KEY, null);
    setMe(null);
    setMode(null);
  }

  useEffect(() => onSignedOut(signOut), []);

  useEffect(() => {
    if (!getToken() || invite) return;
    api("/api/me")
      .then((m) => {
        setMe(m);
        safeSet(ME_KEY, m);
      })
      .catch(() => {}); // offline: keep the saved profile; a 401 signs out via onSignedOut
  }, [invite]);

  async function handleSignOut() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {}
    signOut();
  }

  if (invite) return <AcceptInvite token={invite} onSignedIn={signedIn} />;
  if (!me) return <SignIn onSignedIn={signedIn} />;

  const canField = me.enters_time;
  const canOffice = me.sees_dollars;
  const canTeam = me.role === "gm";
  const canPayroll = me.role === "gm" || me.role === "owner";
  const canMaterials = !DEMO && ["gm", "estimator", "owner", "warehouse"].includes(me.role);
  const views = [
    canField && ["field", "Field"],
    canOffice && ["office", "Jobs"],
    canMaterials && ["materials", "Materials"],
    canPayroll && ["timesheets", "Timesheets"],
    canTeam && ["team", "Team"],
  ].filter(Boolean);
  const view = mode ?? (canOffice ? "office" : canField ? "field" : "materials");

  return (
    <div className="app">
      <DemoBanner />
      <header className="topbar">
        <span className="wordmark small">Courtfield</span>
        {views.length > 1 && (
          <nav className="switch" aria-label="View">
            {views.map(([key, label]) => (
              <button key={key} aria-pressed={view === key} onClick={() => setMode(key)}>
                {label}
              </button>
            ))}
          </nav>
        )}
        <span className="who">
          {me.name}
          <button className="link" onClick={handleSignOut}>
            Sign out
          </button>
        </span>
      </header>
      <main className="content">
        {!canField && !canOffice && !canMaterials ? (
          <p className="empty">Your role doesn't have a screen yet.</p>
        ) : view === "materials" && canMaterials ? (
          <MaterialsView me={me} />
        ) : view === "timesheets" && canPayroll ? (
          <TimesheetView me={me} />
        ) : view === "team" && canTeam ? (
          <TeamView me={me} />
        ) : view === "field" && canField ? (
          <FieldView me={me} />
        ) : (
          <OfficeView me={me} />
        )}
      </main>
    </div>
  );
}
