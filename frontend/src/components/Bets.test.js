import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Bets from "./Bets";
import { backtestFixture as fx, ledgerFixture } from "../test/fixtures";

test("backtest segment lists every bet newest first with P&L", () => {
  render(<MemoryRouter><Bets data={fx} ledger={ledgerFixture} /></MemoryRouter>);
  const rows = within(screen.getByRole("table", { name: "Bet log" })).getAllByRole("row").slice(1);
  expect(rows[0]).toHaveTextContent("Gamma Fighter");
  expect(rows[0]).toHaveTextContent("−$7.17");
  expect(rows[1]).toHaveTextContent("Alpha Fighter");
  expect(rows[1]).toHaveTextContent("+$8.27");
  expect(screen.getByText("$1,132.93")).toBeInTheDocument();
});

test("live segment shows graded and pending picks in bankroll percent", () => {
  render(<MemoryRouter><Bets data={fx} ledger={ledgerFixture} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: /Live/ }));
  expect(screen.getByText("Live Winner")).toBeInTheDocument();
  expect(screen.getAllByText("+0.42%")).toHaveLength(2); // the Net tile and the graded row
  expect(screen.getByText("pending")).toBeInTheDocument();
  expect(screen.getByText(/1 graded/)).toBeInTheDocument();
});

test("live segment has an empty state", () => {
  render(<MemoryRouter><Bets data={fx} ledger={[]} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: /Live/ }));
  expect(screen.getByText(/No live picks graded yet/)).toBeInTheDocument();
});
