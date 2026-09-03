import React, { useState } from "react";
import StatTile from "./StatTile";
import BankrollChart from "./charts/BankrollChart";
import { eventName, money, odds, pct, shortDate, signedMoney, signedPct } from "../format";

const Eyebrow = ({ children }) => (
  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">{children}</p>
);

const RESULT_STYLE = {
  win: "text-up",
  loss: "text-down",
  push: "text-ink-2",
  pending: "text-muted",
};

function Segmented({ value, onChange, counts }) {
  return (
    <div role="group" aria-label="Record" className="inline-flex rounded-md border border-hairline bg-surface p-1">
      {[["backtest", "Backtest"], ["live", "Live"]].map(([key, label]) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          aria-pressed={value === key}
          className={`rounded px-4 py-1.5 text-sm font-medium ${
            value === key ? "bg-ground text-ink" : "text-ink-2 hover:text-ink"
          }`}
        >
          {label} <span className="tnum text-muted">{counts[key]}</span>
        </button>
      ))}
    </div>
  );
}

const Th = ({ children, right }) => (
  <th scope="col" className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted ${right ? "text-right" : "text-left"}`}>
    {children}
  </th>
);
const Td = ({ children, right, className = "" }) => (
  <td className={`px-4 py-3 ${right ? "text-right" : "text-left"} ${className}`}>{children}</td>
);

function BetTable({ rows, live }) {
  return (
    <div className="mt-6 overflow-x-auto rounded-lg border border-hairline bg-surface">
      <table className="tnum w-full text-sm" aria-label="Bet log">
        <thead>
          <tr>
            <Th>Date</Th>
            <Th>Event</Th>
            <Th>Pick</Th>
            <Th>Opponent</Th>
            <Th right>Odds</Th>
            <Th right>Model</Th>
            <Th right>Market</Th>
            <Th right>Edge</Th>
            <Th right>Stake</Th>
            <Th>Result</Th>
            <Th right>P&amp;L</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.event}-${r.fighter}`} className="border-t border-hairline">
              <Td className="whitespace-nowrap text-ink-2">{shortDate(r.date)}</Td>
              <Td className="whitespace-nowrap text-ink-2">{live ? r.event : eventName(r.event)}</Td>
              <Td className="whitespace-nowrap font-medium text-ink">{r.fighter}</Td>
              <Td className="whitespace-nowrap text-ink-2">{r.opponent}</Td>
              <Td right className="text-ink-2">{odds(r.odds)}</Td>
              <Td right className="text-ink-2">{pct(r.model_prob)}</Td>
              <Td right className="text-ink-2">{pct(r.market_prob)}</Td>
              <Td right className="text-ink-2">{signedPct(r.edge * 100)}</Td>
              <Td right className="text-ink-2">{r.stake}</Td>
              <Td className={`font-medium ${RESULT_STYLE[r.result]}`}>{r.result}</Td>
              <Td right className={`font-medium ${r.pnl == null ? "text-muted" : r.pnl >= 0 ? "text-up" : "text-down"}`}>
                {r.pnlText}
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Bets({ data, ledger }) {
  const [segment, setSegment] = useState("backtest");
  // `window` is renamed so it never shadows the browser global
  const { betting, bankroll, bets, window: span } = data;

  const backtestRows = [...bets].reverse().map((b) => ({
    ...b, stake: money(b.stake), pnlText: signedMoney(b.pnl),
  }));

  const graded = ledger.filter((e) => e.result !== "pending");
  const liveWins = graded.filter((e) => e.result === "win").length;
  const netPct = graded.reduce((sum, e) => sum + e.pnl_per_unit * e.stake_pct, 0);
  const cards = new Set(ledger.map((e) => e.event)).size;
  const liveRows = [...ledger]
    .sort((a, b) => (a.event_date < b.event_date ? 1 : -1))
    .map((e) => ({
      ...e,
      date: e.event_date,
      stake: `${e.stake_pct.toFixed(2)}%`,
      pnl: e.pnl_per_unit == null ? null : e.pnl_per_unit * e.stake_pct,
      pnlText: e.pnl_per_unit == null ? "—" : signedPct(e.pnl_per_unit * e.stake_pct, 2),
    }));

  return (
    <main className="mx-auto max-w-content px-6">
      <section className="pb-10 pt-20">
        <Eyebrow>Every bet, graded</Eyebrow>
        <h1 className="mt-4 font-display text-6xl font-bold leading-[0.95] tracking-wide text-ink">Bet log</h1>
        <p className="mt-6 max-w-2xl text-lg text-ink-2">
          The backtest record replays the deployed model over {shortDate(span.start)} to {shortDate(span.end)}{" "}
          at closing odds from a $1,000 paper bankroll. The live record is every pick posted to members, settled
          once results land.
        </p>
        <div className="mt-8">
          <Segmented value={segment} onChange={setSegment} counts={{ backtest: bets.length, live: ledger.length }} />
        </div>
      </section>

      {segment === "backtest" ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Bets" value={betting.bets} sub={`${betting.favorites.total} favorites · ${betting.underdogs.total} underdogs`} />
            <StatTile label="Hit rate" value={pct(betting.hit)} sub={`${betting.favorites.won + betting.underdogs.won} winners`} />
            <StatTile label="Final paper bankroll" value={money(betting.final)} sub="from $1,000 at closing odds" />
            <StatTile
              label="Return"
              value={signedPct(betting.return_pct)}
              tone={betting.return_pct >= 0 ? "up" : "down"}
              sub={`${betting.max_drawdown_pct}% max drawdown`}
            />
          </section>
          <div className="mt-8 rounded-lg border border-hairline bg-surface p-5">
            <BankrollChart points={bankroll} />
          </div>
          <BetTable rows={backtestRows} live={false} />
        </>
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Picks posted" value={ledger.length} sub={`across ${cards} card${cards === 1 ? "" : "s"}`} />
            <StatTile label="Graded" value={graded.length} sub={`${ledger.length - graded.length} pending`} />
            <StatTile label="Hit rate" value={graded.length ? pct(liveWins / graded.length) : "—"} sub={`${liveWins} won of ${graded.length} settled`} />
            <StatTile
              label="Net, % of bankroll"
              value={graded.length ? signedPct(netPct, 2) : "—"}
              tone={netPct >= 0 ? "up" : "down"}
              sub="sum of stake % × payout on graded picks"
            />
          </section>
          {ledger.length === 0 ? (
            <p className="mt-10 max-w-2xl text-ink-2">
              No live picks graded yet. Picks post to members before each card and land here once the results are in.
            </p>
          ) : (
            <BetTable rows={liveRows} live />
          )}
        </>
      )}
    </main>
  );
}
