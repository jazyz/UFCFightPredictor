import backtest from "./data/backtest.json";
import { aggregate, clampWindow, presets, windowRetrains } from "./aggregate";

const CONFIG = { blend_w: 0.8, min_edge: 0.05, kelly_fraction: 0.05, kelly_cap: 0.05, max_dog_odds: 200, start_bankroll: 1000, flat_stake: 10 };

const close = (a, b, tol) => Math.abs(a - b) <= tol;

test("aggregate reproduces the Python summary for the default window", () => {
  const { start, end } = backtest.default_window;
  const js = aggregate(backtest.fights, start, end, backtest.config);
  const py = backtest.summary;
  expect(js.coverage).toEqual(py.coverage);
  ["accuracy", "auc", "log_loss", "brier"].forEach((k) => expect(close(js.metrics[k], py.metrics[k], 1e-4)).toBe(true));
  expect(js.metrics.n).toBe(py.metrics.n);
  py.bands.forEach((b, i) => {
    expect(js.bands[i].label).toBe(b.label);
    expect(js.bands[i].n).toBe(b.n);
    if (b.n) { expect(close(js.bands[i].stated, b.stated, 1e-4)).toBe(true); expect(close(js.bands[i].hit, b.hit, 1e-4)).toBe(true); }
  });
  expect(js.monthly.map((m) => [m.month, m.n])).toEqual(py.monthly.map((m) => [m.month, m.n]));
  py.monthly.forEach((m, i) => expect(close(js.monthly[i].hit, m.hit, 1e-4)).toBe(true));
  py.market.rows.forEach((r, i) => {
    expect(js.market.rows[i].name).toBe(r.name);
    ["accuracy", "auc", "log_loss", "brier"].forEach((k) => expect(close(js.market.rows[i][k], r[k], 1e-4)).toBe(true));
  });
  expect(js.market.agree.n).toBe(py.market.agree.n);
  expect(close(js.market.agree.hit, py.market.agree.hit, 1e-4)).toBe(true);
  expect(js.market.disagree.n).toBe(py.market.disagree.n);
  if (py.market.disagree.model_hit != null) expect(close(js.market.disagree.model_hit, py.market.disagree.model_hit, 1e-4)).toBe(true);
  expect(close(js.flat.market_favorite_per_bet, py.flat.market_favorite_per_bet, 1e-4)).toBe(true);
  expect(close(js.flat.model_pick_per_bet, py.flat.model_pick_per_bet, 1e-4)).toBe(true);
  expect(js.betting.bets).toBe(py.betting.bets);
  expect(js.betting.favorites).toEqual(py.betting.favorites);
  expect(js.betting.underdogs).toEqual(py.betting.underdogs);
  expect(close(js.betting.final, py.betting.final, 0.005)).toBe(true);
  expect(close(js.betting.hit, py.betting.hit, 1e-4)).toBe(true);
  expect(close(js.betting.max_drawdown_pct, py.betting.max_drawdown_pct, 0.05)).toBe(true);
  expect(close(js.betting.low, py.betting.low, 0.005)).toBe(true);
  expect(js.bankroll.length).toBe(py.bankroll.length);
  py.bankroll.forEach((p, i) => {
    expect(close(js.bankroll[i].bankroll, p.bankroll, 0.005)).toBe(true);
    expect(js.bankroll[i].date).toBe(p.date);
    expect(js.bankroll[i].event).toBe(p.event);
  });
  expect(js.bets.length).toBe(py.bets.length);
  py.bets.forEach((b, i) => {
    expect(js.bets[i].fighter).toBe(b.fighter);
    expect(js.bets[i].result).toBe(b.result);
    expect(js.bets[i].odds).toBe(b.odds);
    expect(close(js.bets[i].edge, b.edge, 1e-4)).toBe(true);
    expect(close(js.bets[i].model_prob, b.model_prob, 1e-4)).toBe(true);
    expect(close(js.bets[i].stake, b.stake, 0.005)).toBe(true);
    expect(close(js.bets[i].pnl, b.pnl, 0.005)).toBe(true);
    expect(close(js.bets[i].bankroll_after, b.bankroll_after, 0.005)).toBe(true);
  });
});

const FIGHTS = [
  { date: "2025-01-04", event: "ufc-1", f1: "A", f2: "B", winner: "f1", model_p1: 0.71, market_p1: 0.58, odds1: -150, odds2: 130,
    bet: { side: 1, odds: -150, prob: 0.684, market_prob: 0.58, edge: 0.104, kc: 0.21, stake_frac: 0.0105, payout_mult: 100 / 150 } },
  { date: "2025-01-04", event: "ufc-1", f1: "C", f2: "D", winner: "f2", model_p1: 0.39, market_p1: 0.32, odds1: 200, odds2: -240, bet: null },
  { date: "2025-02-01", event: "ufc-fn", f1: "E", f2: "F", winner: "f2", model_p1: 0.56, market_p1: null, odds1: null, odds2: null, bet: null },
  { date: "2025-02-01", event: "ufc-fn", f1: "G", f2: "H", winner: "unknown", model_p1: null, market_p1: 0.5, odds1: -110, odds2: -110, bet: null },
  { date: "2025-03-01", event: "ufc-2", f1: "A", f2: "B", winner: "push", model_p1: 0.71, market_p1: 0.58, odds1: -150, odds2: 130,
    bet: { side: 1, odds: -150, prob: 0.684, market_prob: 0.58, edge: 0.104, kc: 0.21, stake_frac: 0.0105, payout_mult: 100 / 150 } },
];

test("aggregate on a small fixture: coverage, push handling, compounding", () => {
  const r = aggregate(FIGHTS, "2025-01-01", "2025-12-31", CONFIG);
  expect(r.coverage).toEqual({ fights_in_window: 5, scored: 3, with_odds: 2 });
  expect(r.metrics.n).toBe(3);
  expect(r.metrics.accuracy).toBeCloseTo(2 / 3, 4);
  expect(r.betting.bets).toBe(2);
  expect(r.bets.map((b) => b.result)).toEqual(["win", "push"]);
  expect(r.bets[0].stake).toBeCloseTo(10.5, 2);
  expect(r.bets[0].pnl).toBeCloseTo(7.0, 2);
  expect(r.betting.final).toBeCloseTo(1007.0, 2);
  expect(r.bankroll.map((p) => p.bankroll)).toEqual([1007.0, 1007.0, 1007.0]);
  expect(r.monthly).toEqual([{ month: "2025-01", n: 2, hit: 1 }, { month: "2025-02", n: 1, hit: 0 }]);
});

test("aggregate slices by window and survives an empty window", () => {
  const jan = aggregate(FIGHTS, "2025-01-01", "2025-01-31", CONFIG);
  expect(jan.coverage.fights_in_window).toBe(2);
  expect(jan.betting.bets).toBe(1);
  const empty = aggregate(FIGHTS, "2026-01-01", "2026-01-31", CONFIG);
  expect(empty.coverage).toEqual({ fights_in_window: 0, scored: 0, with_odds: 0 });
  expect(empty.metrics).toEqual({ accuracy: null, auc: null, log_loss: null, brier: null, n: 0 });
  expect(empty.betting.final).toBe(1000);
  expect(empty.betting.hit).toBeNull();
  expect(empty.bets).toEqual([]);
});

test("windowRetrains and presets and clampWindow", () => {
  const range = { start: "2024-01-01", end: "2026-08-30", retrains: ["2024-01-01", "2024-07-13", "2025-01-11", "2025-07-12", "2026-01-24", "2026-07-25"] };
  expect(windowRetrains(range, "2025-01-01", "2025-12-31")).toEqual(["2024-07-13", "2025-01-11", "2025-07-12"]);
  expect(windowRetrains(range, "2024-01-01", "2026-08-30")).toEqual(range.retrains);
  expect(presets(range).map((p) => p[0])).toEqual(["All time", "Last 12 months", "2026 YTD", "2025", "2024"]);
  expect(presets(range)[1]).toEqual(["Last 12 months", "2025-08-30", "2026-08-30"]);
  const fallback = { start: range.start, end: range.end };
  expect(clampWindow(range, "2025-01-01", "2025-12-31", fallback)).toEqual({ start: "2025-01-01", end: "2025-12-31" });
  expect(clampWindow(range, "nope", "2025-12-31", fallback)).toEqual(fallback);
  expect(clampWindow(range, "2025-12-31", "2025-01-01", fallback)).toEqual(fallback);
  expect(clampWindow(range, "2020-01-01", "2030-01-01", fallback)).toEqual(fallback);
  expect(clampWindow(range, null, null, fallback)).toEqual(fallback);
});
