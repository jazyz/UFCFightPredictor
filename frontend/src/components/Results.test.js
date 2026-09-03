import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Results from "./Results";
import { backtestFixture as fx } from "../test/fixtures";

test("results page reports method, coverage, calibration, market and betting", () => {
  render(<MemoryRouter><Results data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("One year out of sample");
  expect(screen.getByText(/547 fights/)).toBeInTheDocument();
  expect(screen.getByText(/2026-02-28/)).toBeInTheDocument();
  expect(screen.getByText("$1,132.93")).toBeInTheDocument();
  expect(screen.getAllByText(/199 bets/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/7.5% max drawdown/).length).toBeGreaterThan(0);
  expect(screen.getByRole("table", { name: "Calibration by confidence band" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Accuracy by month" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Bankroll at month end" })).toBeInTheDocument();
  expect(screen.getByText("Flat $10 per fight")).toBeInTheDocument();
  expect(screen.getByText(/closing line forecasts better than the model\. The return comes from/)).toBeInTheDocument();
});
