import { useLayoutEffect, useRef } from "react";

// A number box that shows commas while you type (65000 -> 65,000) and hands
// back the plain number as a string ("65000"). It's a text box under the hood,
// because number boxes can't show commas; the phone still gets the number pad.

const clean = (s, decimals) => {
  let v = String(s ?? "").replace(/[^\d.]/g, "");
  const dot = v.indexOf(".");
  if (dot >= 0) v = v.slice(0, dot + 1) + v.slice(dot + 1).replace(/\./g, "");
  if (decimals === 0) v = v.replace(".", "");
  else if (dot >= 0 && decimals != null) v = v.slice(0, v.indexOf(".") + 1 + decimals);
  return v.replace(/^0+(?=\d)/, "");
};

export const withCommas = (raw) => {
  if (raw === "" || raw == null) return "";
  const [whole, frac] = String(raw).split(".");
  const w = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return frac === undefined ? w : `${w || "0"}.${frac}`;
};

// How many digits and dots sit left of the cursor; commas don't count.
const keyCharsBefore = (s, pos) => s.slice(0, pos).replace(/[^\d.]/g, "").length;
const posAfterKeyChars = (s, n) => {
  if (n === 0) return 0;
  let seen = 0;
  for (let i = 0; i < s.length; i++) if (/[\d.]/.test(s[i]) && ++seen === n) return i + 1;
  return s.length;
};

export default function NumInput({ value, onChange, decimals = 2, className, ...rest }) {
  const ref = useRef(null);
  const caret = useRef(null);
  const shown = withCommas(value);

  useLayoutEffect(() => {
    const el = ref.current;
    if (caret.current == null || !el || document.activeElement !== el) return;
    const p = posAfterKeyChars(el.value, caret.current);
    el.setSelectionRange(p, p);
    caret.current = null;
  });

  return (
    <input
      {...rest}
      ref={ref}
      type="text"
      inputMode={decimals === 0 ? "numeric" : "decimal"}
      autoComplete="off"
      className={className}
      value={shown}
      onChange={(e) => {
        caret.current = keyCharsBefore(e.target.value, e.target.selectionStart ?? e.target.value.length);
        onChange(clean(e.target.value, decimals));
      }}
    />
  );
}
