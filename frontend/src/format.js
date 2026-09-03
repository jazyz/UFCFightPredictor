const MONTHS = ["january", "february", "march", "april", "may", "june", "july",
  "august", "september", "october", "november", "december"];
const UPPER = { ufc: "UFC", espn: "ESPN", abc: "ABC", fox: "FOX" };

export const pct = (x, digits = 1) => (x == null ? "—" : `${(x * 100).toFixed(digits)}%`);

export const money = (x) =>
  x == null ? "—" : x.toLocaleString("en-US", { style: "currency", currency: "USD" });

export const signedMoney = (x) => `${x < 0 ? "−" : "+"}${money(Math.abs(x))}`;

export const signedPct = (x, digits = 1) => `${x < 0 ? "−" : "+"}${Math.abs(x).toFixed(digits)}%`;

export const odds = (o) => (o > 0 ? `+${o}` : `${o}`);

export function eventName(slug) {
  const words = slug.split("-");
  const cut = words.findIndex((w) => MONTHS.includes(w));
  const kept = cut === -1 ? words : words.slice(0, cut);
  return kept
    .map((w) => UPPER[w] || (w === "on" ? "on" : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

export const shortDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

export function monthLabel(yyyymm) {
  const [y, m] = yyyymm.split("-").map(Number);
  const name = new Date(y, m - 1, 1).toLocaleString("en-US", { month: "short" });
  return `${name} ’${String(y).slice(2)}`;
}

/** Binomial standard error of a hit rate, in percentage points. */
export const stdErrPts = (p, n) => Math.sqrt((p * (1 - p)) / n) * 100;

/** Three-decimal metric, dash for null (empty windows). */
export const num3 = (x) => (x == null ? "—" : x.toFixed(3));
