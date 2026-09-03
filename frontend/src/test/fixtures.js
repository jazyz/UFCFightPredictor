export const backtestFixture = {
  generated: "2026-09-02T14:05:00",
  range: { start: "2024-01-01", end: "2026-08-30", retrains: ["2024-01-01", "2024-07-13", "2025-01-11", "2025-07-12", "2026-01-24", "2026-07-25"] },
  config: { blend_w: 0.8, min_edge: 0.05, kelly_fraction: 0.05, kelly_cap: 0.05, max_dog_odds: 200, start_bankroll: 1000, flat_stake: 10 },
  window: { start: "2025-08-30", end: "2026-08-30", retrains: ["2025-08-30", "2026-02-28", "2026-08-29"] },
  coverage: { fights_in_window: 547, scored: 282, with_odds: 281 },
  metrics: { accuracy: 0.6702, auc: 0.704, log_loss: 0.638, brier: 0.223, n: 282 },
  bands: [
    { label: "50–55%", lo: 0.5, hi: 0.55, n: 60, stated: 0.525, hit: 0.6 },
    { label: "55–60%", lo: 0.55, hi: 0.6, n: 70, stated: 0.575, hit: 0.63 },
    { label: "60–65%", lo: 0.6, hi: 0.65, n: 62, stated: 0.625, hit: 0.629 },
    { label: "65–70%", lo: 0.65, hi: 0.7, n: 68, stated: 0.675, hit: 0.72 },
    { label: "70%+", lo: 0.7, hi: 1.0, n: 22, stated: 0.74, hit: 0.818 },
  ],
  monthly: [
    { month: "2025-09", n: 33, hit: 0.667 },
    { month: "2025-10", n: 30, hit: 0.7 },
  ],
  market: {
    rows: [
      { name: "De-vigged market", accuracy: 0.69, auc: 0.736, log_loss: 0.603, brier: 0.207 },
      { name: "Model (ensemble)", accuracy: 0.673, auc: 0.704, log_loss: 0.638, brier: 0.223 },
      { name: "Blend · 0.8 model + 0.2 market", accuracy: 0.68, auc: 0.73, log_loss: 0.624, brier: 0.217 },
    ],
    agree: { n: 212, hit: 0.741 },
    disagree: { n: 69, model_hit: 0.464 },
  },
  flat: { market_favorite_per_bet: 0.008, model_pick_per_bet: 0.081, stake: 10 },
  betting: {
    final: 1132.93, return_pct: 13.3, bets: 199, hit: 0.618,
    favorites: { won: 102, total: 152 }, underdogs: { won: 21, total: 47 },
    max_drawdown_pct: 7.5, low: 991.5,
  },
  bankroll: [
    { date: "2025-09-06", event: "ufc-fight-night-september-06-2025", bankroll: 1008.27 },
    { date: "2025-09-13", event: "ufc-320", bankroll: 1001.1 },
  ],
  bets: [
    {
      date: "2025-09-06", event: "ufc-fight-night-september-06-2025", fighter: "Alpha Fighter",
      opponent: "Beta Fighter", odds: -150, model_prob: 0.66, market_prob: 0.58, edge: 0.08,
      stake: 12.4, result: "win", pnl: 8.27, bankroll_after: 1008.27, source: "backtest",
    },
    {
      date: "2025-09-13", event: "ufc-320", fighter: "Gamma Fighter", opponent: "Delta Fighter",
      odds: 140, model_prob: 0.48, market_prob: 0.41, edge: 0.07, stake: 7.17, result: "loss",
      pnl: -7.17, bankroll_after: 1001.1, source: "backtest",
    },
  ],
};

/** What aggregate() returns for a window with no scored fights, in page-data shape. */
export const emptyWindowFixture = {
  ...backtestFixture,
  window: { start: "2026-02-01", end: "2026-02-28", retrains: ["2026-01-24"] },
  coverage: { fights_in_window: 0, scored: 0, with_odds: 0 },
  metrics: { accuracy: null, auc: null, log_loss: null, brier: null, n: 0 },
  bands: backtestFixture.bands.map((b) => ({ ...b, n: 0, stated: null, hit: null })),
  monthly: [],
  market: {
    rows: backtestFixture.market.rows.map((r) => ({ ...r, accuracy: null, auc: null, log_loss: null, brier: null })),
    agree: { n: 0, hit: null },
    disagree: { n: 0, model_hit: null },
  },
  flat: { market_favorite_per_bet: 0, model_pick_per_bet: 0, stake: 10 },
  betting: {
    final: 1000, return_pct: 0, bets: 0, hit: null,
    favorites: { won: 0, total: 0 }, underdogs: { won: 0, total: 0 }, max_drawdown_pct: 0, low: 1000,
  },
  bankroll: [],
  bets: [],
};

export const ledgerFixture = [
  {
    event: "UFC Fight Night: Live vs Test", event_date: "2026-09-06", generated: "2026-09-04T02:10:00",
    fighter: "Live Winner", opponent: "Live Loser", odds: -130, model_prob: 0.64, market_prob: 0.56,
    edge: 0.08, kelly: 0.11, stake_pct: 0.55, result: "win", pnl_per_unit: 0.7692, graded: "2026-09-08T02:05:00",
  },
  {
    event: "UFC Fight Night: Live vs Test", event_date: "2026-09-06", generated: "2026-09-04T02:10:00",
    fighter: "Pending Pick", opponent: "Pending Foe", odds: 150, model_prob: 0.47, market_prob: 0.4,
    edge: 0.07, kelly: 0.09, stake_pct: 0.45, result: "pending", pnl_per_unit: null, graded: null,
  },
];
