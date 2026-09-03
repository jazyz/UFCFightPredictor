import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Home from "./Home";
import { backtestFixture as fx, emptyWindowFixture } from "../test/fixtures";

test("home leads with the out-of-sample record and the membership CTA", () => {
  render(<MemoryRouter><Home data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("A UFC model that knows when it's right.");
  expect(screen.getAllByText("67.0%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("81.8%").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/199 bets/).length).toBeGreaterThan(0);
  const ctas = screen.getAllByRole("link", { name: "Get this week's picks" });
  expect(ctas[0]).toHaveAttribute("href", "/join");
  expect(screen.getByRole("link", { name: "See the full results" })).toHaveAttribute("href", "/results");
  expect(screen.getByText(/\$1,000 paper bankroll/)).toBeInTheDocument();
  expect(screen.getAllByText(/281 priced fights/).length).toBeGreaterThan(0);
  expect(screen.getByText(/Between Aug 30, 2025 and Aug 30, 2026 it scored/)).toBeInTheDocument();
  expect(screen.getByText("Flat $10 on the model's pick")).toBeInTheDocument();
  expect(screen.getByText(/Not perfectly monotonic: the 60–65% band hit 62.9% on 62 fights, below the 55–60% band/)).toBeInTheDocument();
});

test("renders an empty window without crashing", () => {
  render(<MemoryRouter><Home data={emptyWindowFixture} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  expect(screen.getByText(/No scored fights fall inside this window/)).toBeInTheDocument();
});
