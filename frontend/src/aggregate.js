// Browser-side twin of testing/export_site_data.py's summary sections. Every function
// here mirrors a Python function by name; aggregate.test.js pins the two together
// against the real payload. Rounding matches the Python export (4 dp rates, cents).

const BANDS = [["50–55%", 0.5, 0.55], ["55–60%", 0.55, 0.6], ["60–65%", 0.6, 0.65], ["65–70%", 0.65, 0.7], ["70%+", 0.7, 1.01]];
const r4 = (x) => Math.round(x * 1e4) / 1e4;
const r2 = (x) => Math.round(x * 100) / 100;
const r1 = (x) => Math.round(x * 10) / 10;
const clip = (p) => Math.min(Math.max(p, 1e-6), 1 - 1e-6);
const ISO = /^\d{4}-\d{2}-\d{2}$/;

function auc(ps, ys) {
  // average-rank Mann–Whitney, identical to sklearn's roc_auc_score
  const order = ps.map((_, i) => i).sort((a, b) => ps[a] - ps[b]);
  const ranks = new Array(ps.length);
  for (let i = 0; i < order.length; ) {
    let j = i;
    while (j + 1 < order.length && ps[order[j + 1]] === ps[order[i]]) j += 1;
    const rank = (i + j) / 2 + 1;
    for (let k = i; k <= j; k += 1) ranks[order[k]] = rank;
    i = j + 1;
  }
  const pos = ys.filter((y) => y === 1).length;
  const neg = ys.length - pos;
  if (!pos || !neg) return null;
  let sumPos = 0;
  ys.forEach((y, i) => { if (y === 1) sumPos += ranks[i]; });
  return (sumPos - (pos * (pos + 1)) / 2) / (pos * neg);
}

function metricsFor(ps, ys) {
  const n = ps.length;
  if (!n) return { accuracy: null, auc: null, log_loss: null, brier: null, n: 0 };
  let acc = 0, ll = 0, br = 0;
  ps.forEach((p, i) => {
    const y = ys[i];
    if ((p >= 0.5) === (y === 1)) acc += 1;
    const q = clip(p);
    ll -= y ? Math.log(q) : Math.log(1 - q);
    br += (q - y) ** 2;
  });
  const a = auc(ps, ys);
  return { accuracy: r4(acc / n), auc: a == null ? null : r4(a), log_loss: r4(ll / n), brier: r4(br / n), n };
}

const pickHit = (f) => (f.model_p1 >= 0.5 ? [f.model_p1, f.winner === "f1"] : [1 - f.model_p1, f.winner === "f2"]);
const y1 = (f) => (f.winner === "f1" ? 1 : 0);
const rate = (hits, n) => (n ? r4(hits / n) : null);

function bands(decided) {
  return BANDS.map(([label, lo, hi]) => {
    const rows = decided.map(pickHit).filter(([c]) => c >= lo && c < hi);
    const n = rows.length;
    return { label, lo, hi: Math.min(hi, 1), n,
      stated: n ? r4(rows.reduce((s, [c]) => s + c, 0) / n) : null,
      hit: n ? r4(rows.filter(([, h]) => h).length / n) : null };
  });
}

function monthly(decided) {
  const by = new Map();
  decided.forEach((f) => { const m = f.date.slice(0, 7); if (!by.has(m)) by.set(m, []); by.get(m).push(pickHit(f)[1]); });
  return [...by.keys()].sort().map((m) => { const h = by.get(m); return { month: m, n: h.length, hit: r4(h.filter(Boolean).length / h.length) }; });
}

function market(priced, blendW) {
  const ys = priced.map(y1);
  const series = [
    ["De-vigged market", priced.map((f) => f.market_p1)],
    ["Model (ensemble)", priced.map((f) => f.model_p1)],
    [`Blend · ${blendW} model + ${r4(1 - blendW)} market`, priced.map((f) => blendW * f.model_p1 + (1 - blendW) * f.market_p1)],
  ];
  const rows = series.map(([name, ps]) => { const m = metricsFor(ps, ys); return { name, accuracy: m.accuracy, auc: m.auc, log_loss: m.log_loss, brier: m.brier }; });
  const agree = priced.filter((f) => (f.model_p1 >= 0.5) === (f.market_p1 >= 0.5));
  const disagree = priced.filter((f) => (f.model_p1 >= 0.5) !== (f.market_p1 >= 0.5));
  const hits = (g) => g.filter((f) => pickHit(f)[1]).length;
  return { rows, agree: { n: agree.length, hit: rate(hits(agree), agree.length) },
    disagree: { n: disagree.length, model_hit: rate(hits(disagree), disagree.length) } };
}

const payout = (odds, stake) => (odds < 0 ? stake * (100 / -odds) : stake * (odds / 100));
function settle(winner, side, odds, stake) {
  if (winner === "push") return ["push", 0];
  if ((winner === "f1") === (side === 1)) return ["win", payout(odds, stake)];
  return ["loss", -stake];
}

function flat(priced, stake) {
  const perBet = (choose) => {
    if (!priced.length) return 0;
    const total = priced.reduce((s, f) => s + settle(f.winner, ...choose(f), stake)[1], 0);
    return r4(total / (stake * priced.length));
  };
  return { market_favorite_per_bet: perBet((f) => (f.market_p1 >= 0.5 ? [1, f.odds1] : [2, f.odds2])),
    model_pick_per_bet: perBet((f) => (f.model_p1 >= 0.5 ? [1, f.odds1] : [2, f.odds2])), stake };
}

function maxDrawdown(series) {
  let peak = series[0], worst = 0;
  series.forEach((x) => { peak = Math.max(peak, x); worst = Math.max(worst, peak ? (peak - x) / peak : 0); });
  return worst;
}

function replay(walk, start) {
  let bankroll = start;
  const points = [], bets = [];
  const won = { fav: 0, dog: 0 }, total = { fav: 0, dog: 0 };
  walk.forEach((f) => {
    if (f.bet) {
      const stake = bankroll * f.bet.stake_frac;
      const [result, pnl] = settle(f.winner, f.bet.side, f.bet.odds, stake);
      bankroll += pnl;
      const side = f.bet.odds < 0 ? "fav" : "dog";
      total[side] += 1;
      if (result === "win") won[side] += 1;
      bets.push({ date: f.date, event: f.event, fighter: f.bet.side === 1 ? f.f1 : f.f2, opponent: f.bet.side === 1 ? f.f2 : f.f1,
        odds: f.bet.odds, model_prob: f.bet.prob, market_prob: f.bet.market_prob, edge: f.bet.edge,
        stake: r2(stake), result, pnl: r2(pnl), bankroll_after: r2(bankroll), source: "backtest" });
    }
    points.push({ date: f.date, event: f.event, bankroll: r2(bankroll) });
  });
  const series = [start, ...points.map((p) => p.bankroll)];
  const n = total.fav + total.dog;
  return { betting: { final: r2(bankroll), return_pct: r1(((bankroll - start) / start) * 100), bets: n,
      hit: rate(won.fav + won.dog, n), favorites: { won: won.fav, total: total.fav }, underdogs: { won: won.dog, total: total.dog },
      max_drawdown_pct: r1(maxDrawdown(series) * 100), low: r2(Math.min(...series)) }, bankroll: points, bets };
}

/** Every summary section for rows with start <= date <= end. Shape matches backtest.summary. */
export function aggregate(fights, start, end, config) {
  const rows = fights.filter((f) => f.date >= start && f.date <= end);
  const scored = rows.filter((f) => f.model_p1 != null);
  const decided = scored.filter((f) => f.winner !== "push");
  const walk = scored.filter((f) => f.market_p1 != null);
  const priced = decided.filter((f) => f.market_p1 != null);
  const { betting, bankroll, bets } = replay(walk, config.start_bankroll);
  return {
    coverage: { fights_in_window: rows.length, scored: decided.length, with_odds: priced.length },
    metrics: metricsFor(decided.map((f) => f.model_p1), decided.map(y1)),
    bands: bands(decided), monthly: monthly(decided), market: market(priced, config.blend_w),
    flat: flat(priced, config.flat_stake), betting, bankroll, bets,
  };
}

/** The retrain in force at the window start, then every retrain inside (start, end]. */
export function windowRetrains(range, start, end) {
  const before = range.retrains.filter((d) => d <= start);
  return [before.length ? before[before.length - 1] : range.retrains[0], ...range.retrains.filter((d) => d > start && d <= end)];
}

/** [label, start, end] presets derived from the data range. */
export function presets(range) {
  const endYear = Number(range.end.slice(0, 4));
  const startYear = Number(range.start.slice(0, 4));
  const list = [["All time", range.start, range.end]];
  const yearAgo = `${endYear - 1}${range.end.slice(4)}`;
  if (yearAgo > range.start) list.push(["Last 12 months", yearAgo, range.end]);
  if (`${endYear}-01-01` > range.start) list.push([`${endYear} YTD`, `${endYear}-01-01`, range.end]);
  for (let y = endYear - 1; y >= startYear; y -= 1) {
    const s = `${y}-01-01`, e = `${y}-12-31`;
    if (e >= range.start) list.push([String(y), s < range.start ? range.start : s, e]);
  }
  return list;
}

/** Validated {start, end} from URL params, else the fallback window. */
export function clampWindow(range, from, to, fallback) {
  if (!from || !to || !ISO.test(from) || !ISO.test(to)) return fallback;
  if (from < range.start || to > range.end || from > to) return fallback;
  return { start: from, end: to };
}
