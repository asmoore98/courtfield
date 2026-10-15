// Nudges crew leads to put the app on their home screen, so it opens like an
// app and loads with no signal. Hidden once installed or dismissed.
import { useEffect, useState } from "react";
import { DEMO, safeGet, safeSet } from "./api";

const KEY = "cf.installHintDismissed";

const isStandalone = () =>
  window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

export default function InstallHint() {
  const [prompt, setPrompt] = useState(null); // Android/Chrome install event
  const [hidden, setHidden] = useState(() => DEMO || isStandalone() || safeGet(KEY, false));

  useEffect(() => {
    const onPrompt = (e) => {
      e.preventDefault();
      setPrompt(e);
    };
    const onInstalled = () => setHidden(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (hidden || (!prompt && !isIOS())) return null;

  const dismiss = () => {
    safeSet(KEY, true);
    setHidden(true);
  };

  return (
    <div className="install" role="note">
      <img src="/icon-192.png" alt="" width="40" height="40" />
      <div className="install-text">
        <b>Put Courtfield on your home screen</b>
        {prompt ? (
          <span>It opens like an app and works on job sites with no signal.</span>
        ) : (
          <span>
            Tap the Share button in Safari, then <b>Add to Home Screen</b>. It opens like an app and works with no signal.
          </span>
        )}
      </div>
      <div className="install-actions">
        {prompt && (
          <button
            className="btn"
            onClick={async () => {
              prompt.prompt();
              const { outcome } = await prompt.userChoice;
              if (outcome === "accepted") setHidden(true);
              setPrompt(null);
            }}
          >
            Install
          </button>
        )}
        <button className="link" onClick={dismiss}>
          Not now
        </button>
      </div>
    </div>
  );
}
