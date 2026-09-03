import { render, screen } from "@testing-library/react";
import CalibrationChart from "./CalibrationChart";
import MonthlyAccuracyChart from "./MonthlyAccuracyChart";
import BankrollChart from "./BankrollChart";
import { backtestFixture as fx } from "../../test/fixtures";

test("calibration chart ships a table twin with every band", () => {
  render(<CalibrationChart bands={fx.bands} />);
  expect(screen.getAllByText("View as table")).toHaveLength(1);
  expect(screen.getByRole("table", { name: "Calibration by confidence band" })).toBeInTheDocument();
  // axis ticks may or may not render in jsdom, so allow more than one match
  expect(screen.getAllByText("70%+").length).toBeGreaterThan(0);
  expect(screen.getAllByText("81.8%").length).toBeGreaterThan(0);
});

test("monthly chart table lists every month", () => {
  render(<MonthlyAccuracyChart monthly={fx.monthly} overall={fx.metrics.accuracy} />);
  expect(screen.getByRole("table", { name: "Accuracy by month" })).toBeInTheDocument();
  expect(screen.getAllByText("Sep ’25").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Oct ’25").length).toBeGreaterThan(0);
});

test("bankroll chart table shows month-end checkpoints", () => {
  render(<BankrollChart points={fx.bankroll} />);
  expect(screen.getByRole("table", { name: "Bankroll at month end" })).toBeInTheDocument();
  expect(screen.getByText("$1,001.10")).toBeInTheDocument();
});
