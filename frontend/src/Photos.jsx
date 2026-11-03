// Photos on a lead or an estimate, straight from the phone's camera roll (or
// the camera). Each photo is shrunk on the phone before it's sent, with a
// small preview for the grid, so it uploads fast on one bar of signal.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, fetchBlob } from "./api";
import { NoteAction, fmtWhen } from "./bits";

const FULL = 2000; // longest side, pixels: plenty to zoom in on a crack
const THUMB = 400;

async function decode(file) {
  try {
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    // older browsers: go through an <img>
    const url = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      return img;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
}

function shrink(img, max, quality) {
  const w = img.width;
  const h = img.height;
  const k = Math.min(1, max / Math.max(w, h));
  const c = document.createElement("canvas");
  c.width = Math.round(w * k);
  c.height = Math.round(h * k);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", quality).split(",")[1];
}

export async function uploadPhoto(kind, id, file) {
  const img = await decode(file);
  const body = { kind, subject_id: id, name: file.name.slice(0, 200), data: shrink(img, FULL, 0.82), thumb: shrink(img, THUMB, 0.7) };
  img.close?.();
  return api("/api/photos", { method: "POST", body });
}

// Photos picked on a new lead go up once the lead is saved.
export async function uploadAll(kind, id, files, onEach) {
  const failed = [];
  for (let i = 0; i < files.length; i++) {
    onEach?.(i + 1, files.length);
    try {
      await uploadPhoto(kind, id, files[i]);
    } catch {
      failed.push(files[i].name);
    }
  }
  return failed;
}

function useBlobUrl(path) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!path) return;
    let live = true;
    let made = null;
    fetchBlob(path)
      .then((b) => {
        made = URL.createObjectURL(b);
        if (live) setUrl(made);
        else URL.revokeObjectURL(made);
      })
      .catch(() => live && setUrl("error"));
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [path]);
  return url;
}

function Thumb({ photo, onOpen }) {
  const url = useBlobUrl(`/api/photos/${photo.id}?size=thumb`);
  return (
    <button type="button" className="ph-thumb" onClick={onOpen} aria-label={`Open photo ${photo.name || ""}`}>
      {url && url !== "error" ? <img src={url} alt="" loading="lazy" /> : <span className="ph-wait">{url === "error" ? "!" : ""}</span>}
      {photo.from === "lead" && <span className="ph-tag">Lead</span>}
    </button>
  );
}

function LocalThumb({ file }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  return <span className="ph-thumb is-pending">{url && <img src={url} alt="" />}</span>;
}

function Viewer({ photo, onClose, onRemoved }) {
  const url = useBlobUrl(`/api/photos/${photo.id}`);
  // Drawn on top of the page, outside any form it sits in (the lead form),
  // and its own Remove box never submits the form behind it.
  return createPortal(
    <div className="ph-viewer" role="dialog" aria-modal="true" aria-label="Photo" onClick={onClose} onSubmit={(e) => e.stopPropagation()}>
      <div className="ph-frame" onClick={(e) => e.stopPropagation()}>
        {url && url !== "error" ? <img src={url} alt={photo.name} /> : <p className="empty">{url === "error" ? "Couldn't load the photo." : "Loading…"}</p>}
        <div className="ph-info">
          <span>
            {photo.from === "lead" && <b>From the lead · </b>}
            {photo.by} · {fmtWhen(photo.at)}
          </span>
          <span className="ph-actions">
            {url && url !== "error" && (
              <a className="btn-ghost" href={url} download={photo.name || "photo.jpg"}>
                Save
              </a>
            )}
            {photo.can_remove && (
              <NoteAction
                label="Remove"
                tone="danger"
                prompt="Why remove it?"
                placeholder="e.g. Wrong job, blurry"
                onSubmit={(reason) => api(`/api/photos/${photo.id}/remove`, { method: "POST", body: { reason } }).then(onRemoved)}
              />
            )}
            <button type="button" className="btn" onClick={onClose}>
              Close
            </button>
          </span>
        </div>
      </div>
    </div>,
    document.body
  );
}

/* The photo grid with an "Add photos" button. With no `id` yet (a new
   lead), picked photos wait in `pending` and go up when it's saved. */
export default function Photos({ kind, id, canAdd = true, pending, onPending, title = "Photos" }) {
  const [list, setList] = useState(null);
  const [n, setN] = useState(0);
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState(null); // "Adding 2 of 5…"
  const [error, setError] = useState(null);
  const input = useRef(null);
  const reload = () => setN((x) => x + 1);

  useEffect(() => {
    if (!id) return;
    api(`/api/photos?kind=${kind}&id=${id}`)
      .then(setList)
      .catch((e) => setError(e.message));
  }, [kind, id, n]);

  async function picked(files) {
    setError(null);
    if (!files.length) return;
    if (!id) return onPending?.([...(pending ?? []), ...files]);
    const failed = await uploadAll(kind, id, files, (i, total) => setBusy(`Adding ${i} of ${total}…`));
    setBusy(null);
    if (failed.length) setError(`${failed.length} photo${failed.length > 1 ? "s" : ""} didn't go up (no signal?). Add ${failed.length > 1 ? "them" : "it"} again.`);
    reload();
  }

  const shown = list ?? [];
  return (
    <div className="photos">
      <div className="panel-head">
        <h3>{title}</h3>
        {canAdd && (
          <>
            <button type="button" className="btn-ghost" onClick={() => input.current?.click()} disabled={!!busy}>
              {busy ?? "Add photos"}
            </button>
            <input
              ref={input}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) => {
                picked([...e.target.files]);
                e.target.value = "";
              }}
            />
          </>
        )}
      </div>
      {!id && pending?.length > 0 && (
        <>
          <div className="ph-grid">
            {pending.map((f, i) => (
              <LocalThumb key={i} file={f} />
            ))}
          </div>
          <p className="help">
            {pending.length} photo{pending.length > 1 ? "s" : ""} will upload when you save.{" "}
            <button type="button" className="link" onClick={() => onPending([])}>
              Clear
            </button>
          </p>
        </>
      )}
      {id && list && !shown.length && <p className="help">No photos yet.{canAdd ? " Tap Add photos to pick from the camera roll or take one." : ""}</p>}
      {!id && !pending?.length && canAdd && <p className="help">Pick from the camera roll or take one. They upload when you save.</p>}
      {shown.length > 0 && (
        <div className="ph-grid">
          {shown.map((p) => (
            <Thumb key={p.id} photo={p} onOpen={() => setOpen(p)} />
          ))}
        </div>
      )}
      {error && <p className="err">{error}</p>}
      {open && (
        <Viewer
          photo={open}
          onClose={() => setOpen(null)}
          onRemoved={() => {
            setOpen(null);
            reload();
          }}
        />
      )}
    </div>
  );
}
