import React from "react";
import { Link } from "react-router-dom";
import { MEMBERSHIP_URL } from "../constants";
import { pct } from "../format";

export default function Join({ data }) {
  const { metrics, bands, config } = data;
  const top = bands[bands.length - 1];
  const cards = [
    ["Every covered bout", "Win probability for each fight the model can score, with the de-vigged market probability beside it."],
    ["Edge and stake", `Which side clears the ${Math.round(config.min_edge * 100)}-point edge gate, and the fractional Kelly stake as a percent of bankroll.`],
    ["Graded in public", "Every pick lands on the bet log once results are in. Wins and losses alike."],
  ];
  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-12 pt-20">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Membership</p>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">Get the picks</h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          The model that scored {pct(metrics.accuracy)} on {metrics.n} out-of-sample fights, and hit {pct(top.hit)}{" "}
          on its most confident calls, runs on every upcoming card. Members see its output before the fights.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {cards.map(([title, body]) => (
          <div key={title} className="rounded-lg border border-hairline bg-surface p-6">
            <h2 className="font-display text-2xl font-bold tracking-wide text-ink">{title}</h2>
            <p className="mt-2 text-ink-2">{body}</p>
          </div>
        ))}
      </section>

      <section className="mt-16 rounded-lg border border-hairline bg-surface p-8 sm:p-12">
        <a
          href={MEMBERSHIP_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-block rounded-md bg-accent px-8 py-4 text-lg font-semibold text-white hover:bg-accent-hover"
        >
          Join UFC Alpha
        </a>
        <p className="mt-6 max-w-2xl text-sm text-ink-2">
          Picks are model output for informational purposes, not betting advice. Past performance does not
          guarantee future results. You must be of legal gambling age in your jurisdiction. Not sure yet? Read the{" "}
          <Link to="/results" className="text-ink underline hover:text-accent">full results</Link> first.
        </p>
      </section>
    </main>
  );
}
