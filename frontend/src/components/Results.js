import React from "react";
import StatTile from "./StatTile";
import CalibrationChart from "./charts/CalibrationChart";
import MonthlyAccuracyChart from "./charts/MonthlyAccuracyChart";
import BankrollChart from "./charts/BankrollChart";
import { money, monthLabel, pct, shortDate, signedPct, stdErrPts } from "../format";

const Eyebrow = ({ children }) => (
  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{children}</p>
);
const H2 = ({ children }) => (
  <h2 className="mt-2 font-display text-4xl font-bold leading-none tracking-wide text-ink">{children}</h2>
);
const Card = ({ children }) => (
  <div className="mt-8 rounded-lg border border-hairline bg-surface p-5">{children}</div>
);

export default function Results({ data }) {
  // `window` is renamed so it never shadows the browser global
  const { window: span, coverage, metrics, bands, monthly, market, flat, betting, bankroll } = data;
  const top = bands[bands.length - 1];
  const retrains = span.retrains.slice(1);
  const se = stdErrPts(metrics.accuracy, metrics.n);
  const months = monthly.map((m) => m.hit);
  const worst = monthly[months.indexOf(Math.min(...months))];
  const best = monthly[months.indexOf(Math.max(...months))];
  const [marketRow, modelRow] = market.rows;
  const marketSharper = marketRow.log_loss < modelRow.log_loss;
  const modelMoreAccurate = modelRow.accuracy > marketRow.accuracy;

  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-12 pt-20">
        <Eyebrow>
          Annual model review · {shortDate(span.start)} → {shortDate(span.end)} · generated {data.generated.slice(0, 10)}
        </Eyebrow>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">
          One year out of sample
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          How the deployed model performed between {shortDate(span.start)} and {shortDate(span.end)}, a
          window it never trained on: {metrics.n} fights scored walk-forward, graded on accuracy,
          calibration, and what a $1,000 paper bankroll did against real closing odds.
        </p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Accuracy" value={pct(metrics.accuracy)} sub={`${metrics.n} out-of-sample fights`} />
        <StatTile
          label="Kelly return"
          value={signedPct(betting.return_pct)}
          tone={betting.return_pct >= 0 ? "up" : "down"}
          sub={`${betting.bets} bets · ${betting.max_drawdown_pct}% max drawdown`}
        />
        <StatTile label="AUC" value={metrics.auc.toFixed(3)} sub={`log loss ${metrics.log_loss.toFixed(3)} · Brier ${metrics.brier.toFixed(3)}`} />
        <StatTile label="70%+ confidence" value={pct(top.hit)} sub={`hit rate on ${top.n} high-conviction picks`} />
      </section>

      <section className="mt-20">
        <Eyebrow>Method</Eyebrow>
        <H2>No peeking</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          Every prediction comes from a model that had never seen the fight, or anything after it. The ensemble
          trained on fights before {shortDate(span.start)}, then retrained on{" "}
          {retrains.map(shortDate).join(" and ")} as the year advanced. Production retrains twice a week, so the
          live model is fresher than the one tested here. One hyperparameter set, tuned once on the full dataset,
          is shared by every retrain: the walk-forward isolates training data, not hyperparameter selection.
        </p>
        <p className="mt-4 max-w-2xl text-ink-2">
          Coverage: the window had {coverage.fights_in_window} fights with recorded results. The model scored{" "}
          {coverage.scored} of them and skipped the rest, mostly by design: women's bouts are excluded from the training
          data, both fighters need at least two prior UFC fights, and draws and no contests are not graded.
          Betting uses the {coverage.with_odds} scored fights with usable closing odds, de-vigged to remove the
          bookmaker's margin.
        </p>
      </section>

      <section className="mt-20">
        <Eyebrow>Calibration</Eyebrow>
        <H2>When it says 70%, does it win 70%?</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          For Kelly sizing the question is not "how often is it right" but whether stated confidence tracks
          reality. Stated confidence against actual hit rate, by the model's pre-fight win probability.
        </p>
        <Card><CalibrationChart bands={bands} /></Card>
      </section>

      <section className="mt-20">
        <Eyebrow>By month</Eyebrow>
        <H2>Accuracy by month</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          Month-to-month swings ({pct(worst.hit, 0)} in {monthLabel(worst.month)} to {pct(best.hit, 0)} in {monthLabel(best.month)}) are
          what {Math.min(...monthly.map((m) => m.n))} to {Math.max(...monthly.map((m) => m.n))} fight samples do.
          The reference line is the year's hit rate, {pct(metrics.accuracy, 0)}.
        </p>
        <Card><MonthlyAccuracyChart monthly={monthly} overall={metrics.accuracy} /></Card>
      </section>

      <section className="mt-20">
        <Eyebrow>Versus the market</Eyebrow>
        <H2>Model, market, and the blend that bets</H2>
        <div className="mt-8 overflow-x-auto rounded-lg border border-hairline bg-surface">
          <table className="tnum w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Forecaster</th>
                <th className="px-5 py-3 font-semibold">Accuracy</th>
                <th className="px-5 py-3 font-semibold">AUC</th>
                <th className="px-5 py-3 font-semibold">Log loss</th>
                <th className="px-5 py-3 font-semibold">Brier</th>
              </tr>
            </thead>
            <tbody>
              {market.rows.map((r) => (
                <tr key={r.name} className="border-t border-hairline">
                  <td className="px-5 py-3 text-ink">{r.name}</td>
                  <td className="px-5 py-3 text-ink-2">{pct(r.accuracy)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.auc.toFixed(3)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.log_loss.toFixed(3)}</td>
                  <td className="px-5 py-3 text-ink-2">{r.brier.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-6 max-w-2xl text-ink-2">
          On the {coverage.with_odds} priced fights, the model and the market favor the same fighter{" "}
          {market.agree.n} times, and those picks hit {pct(market.agree.hit)}. On the {market.disagree.n} fights
          where they disagree, the model wins {pct(market.disagree.model_hit)}. A bettor does not need to
          out-predict the market, only to find prices that pay more than a calibrated probability says they should.
        </p>
      </section>

      <section className="mt-20">
        <Eyebrow>Betting</Eyebrow>
        <H2>{signedPct(betting.return_pct)} on a $1,000 paper bankroll</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          The production config bets the model's pick with fractional Kelly (5% fraction, 5% cap, no floor)
          whenever the blended probability beats the de-vigged price by at least 5 points. {betting.bets} bets,{" "}
          {betting.max_drawdown_pct}% max drawdown, low point {money(betting.low)}.
        </p>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="Final bankroll" value={money(betting.final)} sub={`from $1,000 · ${betting.bets} bets`} />
          <StatTile label="Hit rate" value={pct(betting.hit)} sub={`${betting.favorites.won}/${betting.favorites.total} favorites · ${betting.underdogs.won}/${betting.underdogs.total} underdogs`} />
          <StatTile label="Max drawdown" value={`${betting.max_drawdown_pct}%`} sub={`low point ${money(betting.low)}`} />
          <StatTile
            label={`Flat $${flat.stake} per fight`}
            value={`${signedPct(flat.model_pick_per_bet * 100)} / bet`}
            tone={flat.model_pick_per_bet >= 0 ? "up" : "down"}
            sub={`model pick over ${coverage.with_odds} fights · favorite ${signedPct(flat.market_favorite_per_bet * 100)} / bet`}
          />
        </div>
        <Card><BankrollChart points={bankroll} /></Card>
      </section>

      <section className="mt-20">
        <Eyebrow>Analysis</Eyebrow>
        <H2>Why this works, and where it doesn't</H2>
        <ul className="mt-6 max-w-2xl list-disc space-y-3 pl-5 text-ink-2">
          <li>
            <b className="text-ink">The edge is price selection, not prophecy.</b>{" "}
            {marketSharper
              ? "On the proper scoring rules (AUC, log loss, Brier) the closing line forecasts better than the model"
              : "On the proper scoring rules (AUC, log loss, Brier) the model forecasts at least as well as the closing line"}
            {modelMoreAccurate ? ", even in a year where the model edged it on raw accuracy" : ""}. The return comes from
            which agreements the model sizes up: fights where its calibrated probability says the price is soft.
          </li>
          <li>
            <b className="text-ink">Disagreement is a warning sign.</b> When model and market split, the model wins{" "}
            {pct(market.disagree.model_hit)}. Large gaps usually mean the market knows something a career-stats
            model structurally cannot: injuries, short-notice replacements, weight-cut news.
          </li>
          <li>
            <b className="text-ink">Calibration is the asset to protect.</b> Accuracy barely separates a good year
            from a bad one. What makes betting work is that stated confidence tracked reality band by band.
          </li>
          <li>
            <b className="text-ink">Honest error bars.</b> {pct(metrics.accuracy)} on {metrics.n} fights carries a
            ±{se.toFixed(1)}-point standard error; the return rides on {betting.bets} bets and their sequencing.
          </li>
          <li>
            <b className="text-ink">Coverage is the ceiling.</b> The model acts on{" "}
            {pct(coverage.scored / coverage.fights_in_window, 0)} of fights. The largest untapped improvement is
            not a better model but a wider one.
          </li>
        </ul>
      </section>
    </main>
  );
}
