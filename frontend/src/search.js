// Find library entries by any of their names, words in any order.
// "cleaning court", "court clean" and "clean court" all find "Court cleaning".
// It only suggests: every match is listed and the person picks one.

const STOP = new Set(["and", "the", "of", "a", "an", "to", "for", "with", "on", "in"]);

// Rough word root so "cleaning", "cleans" and "cleaned" all match "clean".
export function stem(w) {
  w = w.toLowerCase();
  for (const end of ["ings", "ing", "ies", "ers", "er", "ed", "es", "s"]) {
    if (w.length > end.length + 2 && w.endsWith(end)) return end === "ies" ? w.slice(0, -3) + "y" : w.slice(0, -end.length);
  }
  return w;
}

export const words = (text) =>
  String(text ?? "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .split(/[^a-z0-9]+/)
    .filter((w) => w && !STOP.has(w))
    .map(stem);

// How well one name matches the query words: every query word must start a
// word in the name. Whole-word hits score higher than partial ones.
function scoreName(qw, name) {
  const nw = words(name);
  if (!qw.length) return 0;
  let score = 0;
  for (const q of qw) {
    let best = 0;
    for (const w of nw) {
      if (w === q) best = Math.max(best, 3);
      else if (w.startsWith(q)) best = Math.max(best, 2);
      else if (w.length >= 4 && q.startsWith(w)) best = Math.max(best, 2); // "grade" finds "grading"
      else if (q.length >= 4 && w.includes(q)) best = Math.max(best, 1);
    }
    if (!best) return 0;
    score += best;
  }
  // a name made of exactly the query words, in any order, is the best match
  if (nw.length === qw.length) score += 2;
  return score;
}

/* Matches for `query` among entries with { name, aliases?: [] }. Each result
   is { entry, via } where `via` is the other name that matched, if any. */
export function searchEntries(query, entries, limit = 12) {
  const qw = words(query);
  if (!qw.length) return entries.slice(0, limit).map((entry) => ({ entry, via: null }));
  const out = [];
  for (const entry of entries) {
    let best = scoreName(qw, entry.name) * 2; // the official name counts double
    let via = null;
    for (const a of entry.aliases ?? []) {
      const s = scoreName(qw, a);
      if (s > best) {
        best = s;
        via = a;
      }
    }
    if (best > 0) out.push({ entry, via, score: best });
  }
  out.sort((a, b) => b.score - a.score || a.entry.name.localeCompare(b.entry.name));
  return out.slice(0, limit);
}

export const sameName = (a, b) => words(a).join(" ") === words(b).join(" ");
