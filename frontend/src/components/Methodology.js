import React from "react";
import { GITHUB_URL } from "../constants";
import { pct } from "../format";

const Section = ({ eyebrow, title, children }) => (
  <section className="mt-16">
    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{eyebrow}</p>
    <h2 className="mt-2 font-display text-4xl font-bold leading-none tracking-wide text-ink">{title}</h2>
    <div className="mt-4 max-w-2xl space-y-4 text-ink-2">{children}</div>
  </section>
);

export default function Methodology({ data }) {
  // `window` is renamed so it never shadows the browser global
  const { coverage, metrics, window: span } = data;
  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-4 pt-20">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Methodology</p>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">How the model works</h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          A career-statistics model for UFC fights, built to be tested the hard way: on fights it has never seen,
          against the closing line. The code is public.
        </p>
      </section>

      <Section eyebrow="Data" title="Every fight since 1994">
        <p>
          Fight-level statistics are scraped from ufcstats.com: significant strikes by target and position,
          takedowns, submission attempts, reversals, control time, knockdowns, method and round of finish.
          Both fighters need at least two prior UFC bouts on record; debutants and anyone with less history
          are skipped rather than guessed.
        </p>
        <p>
          The cleaning step drops women's bouts, so the model never trains on or predicts them. Widening
          coverage is the largest open improvement.
        </p>
      </Section>

      <Section eyebrow="Features" title="180+ signals per fighter, frozen at fight time">
        <p>
          For each base statistic the pipeline derives per-minute rates, accuracy, differentials against the
          opponent, and career totals, then rolls them into weighted averages that favor recent fights. An ELO
          rating tracks quality of opposition. Height, reach, age and stance round it out.
        </p>
        <p>
          Every feature for a fight is computed from bouts that preceded it. Nothing from the fight itself or
          from later fights leaks in. Skipping this step is how a predictor reports 80% accuracy and then loses
          money.
        </p>
      </Section>

      <Section eyebrow="Model" title="A five-model LightGBM ensemble">
        <p>
          Five gradient-boosted tree models, each with its own Optuna-tuned hyperparameters, are averaged at
          inference. Training data is mirrored so the model sees every fight from both corners, correlated
          features are pruned in pairs so the mirror stays intact, and every published probability averages
          both orientations of the bout, so which fighter is listed first does not tip the answer.
        </p>
        <p>
          The output is a win probability. Judged on {metrics.n} out-of-sample fights it scores{" "}
          {pct(metrics.accuracy)} accuracy, {metrics.auc.toFixed(3)} AUC and a {metrics.brier.toFixed(3)} Brier
          score. Calibration, not accuracy, is what the retraining schedule protects.
        </p>
      </Section>

      <Section eyebrow="Evaluation" title="Walk-forward, never in-sample">
        <p>
          The published record trains on fights before {span.start}, then retrains on the production cadence
          as the window advances, so every prediction comes from a model that stopped learning before the fight.
          Of {coverage.fights_in_window} fights in the window, {coverage.scored} were scorable.
        </p>
        <p>
          Betting is replayed with the exact production sizing code: fractional Kelly at 5% of the criterion,
          capped at 5% of bankroll, no floor, and a 5-point minimum edge measured against the de-vigged closing
          price. The bet log shows every stake.
        </p>
      </Section>

      <Section eyebrow="Operations" title="Retrained twice a week">
        <p>
          A scheduled job scrapes new results, rebuilds every feature from scratch for ELO consistency, retrains
          the ensemble, and validates it on a chronological holdout before it can replace the previous models.
          The same job grades the public bet ledger.
        </p>
        <p>
          Everything described here is in the repository:{" "}
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="text-ink underline hover:text-accent">
            UFC Alpha on GitHub
          </a>
          .
        </p>
      </Section>
    </main>
  );
}
