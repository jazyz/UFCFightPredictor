import React from "react";
import { Link } from "react-router-dom";
import StatTile from "./StatTile";
import CalibrationChart from "./charts/CalibrationChart";
import { num3, pct, shortDate, signedPct, stdErrPts } from "../format";

const Eyebrow = ({ children }) => (
  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{children}</p>
);

const H2 = ({ children }) => (
  <h2 className="mt-2 font-display text-4xl font-bold leading-none tracking-wide text-ink">{children}</h2>
);

const CtaButton = ({ children }) => (
  <Link
    to="/join"
    className="inline-block rounded-md bg-accent px-6 py-3 text-base font-semibold text-white hover:bg-accent-hover"
  >
    {children}
  </Link>
);

export default function Home({ data }) {
  // `window` is renamed so it never shadows the browser global
  const { metrics, bands, market, flat, betting, coverage, window: span, config } = data;
  const steps = [
    ["Data", "Every UFC fight since 1994, scraped from ufcstats.com: strikes, takedowns, control time, finishes. Each fight is described only by what was known before it happened."],
    ["Model", "180+ engineered features per fighter feed a five-model LightGBM ensemble retrained twice a week. It outputs a win probability, not a hot take."],
    ["Bets", `Probability meets closing odds. A fractional Kelly stake goes down only when the blended probability's edge over the de-vigged market clears ${Math.round(config.min_edge * 100)}%, and never on a price longer than +${config.max_dog_odds}.`],
  ];
  const top = bands[bands.length - 1];
  const populated = bands.filter((b) => b.n > 0);
  const climbs = populated.every((b, i) => i === 0 || b.hit >= populated[i - 1].hit);
  const modelBeatsFavorites = flat.model_pick_per_bet > flat.market_favorite_per_bet;
  const se = metrics.n ? stdErrPts(metrics.accuracy, metrics.n) : null;

  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-16 pt-20">
        <Eyebrow>Out-of-sample · walk-forward · closing odds</Eyebrow>
        <h1 className="mt-4 max-w-4xl font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink sm:text-7xl">
          A UFC model that knows when it's right.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          Between {shortDate(span.start)} and {shortDate(span.end)} it scored <b className="text-ink">{metrics.n}</b> fights it had never
          seen and called <b className="text-ink">{pct(metrics.accuracy)}</b> of them. When it said 70% or
          better, it hit <b className="text-ink">{pct(top.hit)}</b>.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <CtaButton>Get this week's picks</CtaButton>
          <Link
            to="/results"
            className="inline-block rounded-md border border-hairline px-6 py-3 text-base font-semibold text-ink hover:bg-surface"
          >
            See the full results
          </Link>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Out-of-sample accuracy"
          value={pct(metrics.accuracy)}
          sub={`${metrics.n} fights · ${shortDate(span.start)} to ${shortDate(span.end)}`}
        />
        <StatTile
          label="70%+ confidence picks"
          value={pct(top.hit)}
          sub={`${top.n} picks · stated ${pct(top.stated)} on average`}
        />
        <StatTile
          label={`Flat $${flat.stake} on the model's pick`}
          value={`${signedPct(flat.model_pick_per_bet * 100)} / bet`}
          tone={flat.model_pick_per_bet >= 0 ? "up" : "down"}
          sub={`${coverage.with_odds} priced fights, $${flat.stake} each · blindly backing the favorite: ${signedPct(flat.market_favorite_per_bet * 100)} / bet`}
        />
        <StatTile
          label="Kelly paper bankroll"
          value={signedPct(betting.return_pct)}
          tone={betting.return_pct >= 0 ? "up" : "down"}
          sub={`${betting.bets} bets · ${betting.max_drawdown_pct}% max drawdown · $1,000 start`}
        />
      </section>

      <section className="mt-24">
        <Eyebrow>How it works</Eyebrow>
        <H2>Three steps, no vibes</H2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {steps.map(([title, body]) => (
            <div key={title} className="rounded-lg border border-hairline bg-surface p-6">
              <h3 className="font-display text-2xl font-bold tracking-wide text-ink">{title}</h3>
              <p className="mt-2 text-ink-2">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-24">
        <Eyebrow>Calibration</Eyebrow>
        <H2>Confidence you can size a bet on</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          Kelly sizing only works if "70%" means 70%. This chart puts the model's stated confidence beside
          what actually happened, band by band.{" "}
          {climbs
            ? "The bars climb together: the more confident the model, the more often it is right."
            : "The higher bands mostly hit more often; the small bands wobble, and that is what small samples do."}{" "}
          That is the property a stale model loses first, and the reason the ensemble is retrained twice a week.
        </p>
        <div className="mt-8 rounded-lg border border-hairline bg-surface p-5">
          <CalibrationChart bands={bands} />
        </div>
      </section>

      <section className="mt-24">
        <Eyebrow>Versus the market</Eyebrow>
        <H2>{modelBeatsFavorites ? "The market predicts well. The model still finds prices." : "The market is sharp. So is the model."}</H2>
        <p className="mt-4 max-w-2xl text-ink-2">
          On <b className="text-ink">{market.agree.n}</b> of {coverage.with_odds} priced fights, the model and the
          closing line pick the same fighter, and those picks hit <b className="text-ink">{pct(market.agree.hit)}</b>.
          Where they disagree ({market.disagree.n} fights) the model wins {pct(market.disagree.model_hit)}. Sharp
          lines price injuries, camp changes and late news that a career-stats model never sees.{" "}
          {modelBeatsFavorites
            ? `The edge is not out-predicting the market. It is knowing which prices are soft: a flat $${flat.stake} on every model pick across those ${coverage.with_odds} fights returned ${signedPct(flat.model_pick_per_bet * 100)} per bet, against ${signedPct(flat.market_favorite_per_bet * 100)} for the favorite.`
            : `At flat stakes across those ${coverage.with_odds} fights, the model's picks returned ${signedPct(flat.model_pick_per_bet * 100)} per bet against ${signedPct(flat.market_favorite_per_bet * 100)} for blindly backing the favorite.`}
        </p>
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
                  <td className="px-5 py-3 text-ink-2">{num3(r.auc)}</td>
                  <td className="px-5 py-3 text-ink-2">{num3(r.log_loss)}</td>
                  <td className="px-5 py-3 text-ink-2">{num3(r.brier)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-24 rounded-lg border border-hairline bg-surface p-8 sm:p-12">
        <Eyebrow>Membership</Eyebrow>
        <H2>Every pick for the next card, before it starts</H2>
        <ul className="mt-6 max-w-2xl list-disc space-y-2 pl-5 text-ink-2">
          <li>Model probability, de-vigged market probability, edge and Kelly stake for every bout the model covers.</li>
          <li>Posted before the card. Graded publicly on the bet log afterwards.</li>
          <li>The same numbers the backtest was scored on. Nothing hand-picked.</li>
        </ul>
        <div className="mt-8">
          <CtaButton>Get this week's picks</CtaButton>
        </div>
      </section>

      <section className="mt-24">
        <Eyebrow>Read the fine print</Eyebrow>
        <H2>What this record does not prove</H2>
        <ul className="mt-6 max-w-2xl list-disc space-y-3 pl-5 text-ink-2">
          <li>
            <b className="text-ink">Sample size.</b> {pct(metrics.accuracy)} on {metrics.n} fights carries a
            ±{se == null ? "—" : se.toFixed(1)}-point standard error. Treat the direction as meaningful, not the second digit.
          </li>
          <li>
            <b className="text-ink">Coverage.</b> The model scored {coverage.scored} of {coverage.fights_in_window}{" "}
            fights in the window. It skips women's bouts, debutants, and anyone with fewer than two UFC fights.
          </li>
          <li>
            <b className="text-ink">Paper money.</b> Every return here is a $1,000 paper bankroll replayed against
            closing odds, with {betting.bets} bets and a {betting.max_drawdown_pct}% max drawdown. Real limits,
            line movement and fees will differ.
          </li>
        </ul>
      </section>
    </main>
  );
}
