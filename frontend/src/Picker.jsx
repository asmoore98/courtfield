// A text box that searches a list as you type and shows the matches under it.
// It never picks for you: tap a match (or arrow + Enter) to choose it, or keep
// what you typed. Used for library tasks and price-list materials.
import { useEffect, useId, useRef, useState } from "react";
import { searchEntries } from "./search";

export default function Picker({
  value,
  onChange, // (text) => void, called as you type
  options, // [{ id, name, aliases? }]
  onPick, // (entry) => void
  renderOption, // (entry, via) => element
  footer, // (text, close) => element under the matches (e.g. "use as typed")
  placeholder,
  invalid,
  label, // screen-reader label
  emptyHint = "Type to search",
  noMatchText = "No match in the list.",
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const wrap = useRef(null);
  const results = open ? searchEntries(value, options ?? [], 10) : [];

  useEffect(() => setActive(0), [value]);
  useEffect(() => {
    if (!open) return;
    const away = (e) => wrap.current && !wrap.current.contains(e.target) && setOpen(false);
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  const pick = (entry) => {
    onPick(entry);
    setOpen(false);
  };
  const close = () => setOpen(false);

  function onKey(e) {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) return setOpen(true);
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      pick(results[active].entry);
    } else if (e.key === "Escape" || e.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div className="picker" ref={wrap}>
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={(e) => {
          if (!wrap.current?.contains(e.relatedTarget)) setOpen(false);
        }}
        onKeyDown={onKey}
        placeholder={placeholder}
        aria-label={label}
        aria-invalid={invalid || undefined}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
      />
      {open && (
        <div className="picker-pop" id={listId} role="listbox">
          {!value.trim() && <p className="picker-hint">{emptyHint}</p>}
          {results.map(({ entry, via }, i) => (
            <button
              type="button"
              key={entry.id}
              role="option"
              aria-selected={i === active}
              className={i === active ? "picker-opt is-active" : "picker-opt"}
              onPointerDown={(e) => e.preventDefault()}
              onClick={() => pick(entry)}
              onPointerEnter={() => setActive(i)}
            >
              {renderOption ? renderOption(entry, via) : entry.name}
            </button>
          ))}
          {value.trim() && !results.length && <p className="picker-hint">{noMatchText}</p>}
          {footer && <div className="picker-foot">{footer(value.trim(), close)}</div>}
        </div>
      )}
    </div>
  );
}
