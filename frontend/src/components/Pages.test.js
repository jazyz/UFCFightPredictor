import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Methodology from "./Methodology";
import Join from "./Join";
import { GITHUB_URL, MEMBERSHIP_URL } from "../constants";
import { backtestFixture as fx } from "../test/fixtures";

test("methodology explains the pipeline and links the source", () => {
  render(<MemoryRouter><Methodology data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("How the model works");
  expect(screen.getByText(/five-model LightGBM/i)).toBeInTheDocument();
  expect(screen.getByText(/women's bouts/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /GitHub/ })).toHaveAttribute("href", GITHUB_URL);
});

test("join page sends members to the paywall", () => {
  render(<MemoryRouter><Join data={fx} /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Get the picks");
  expect(screen.getByRole("link", { name: "Join UFC Alpha" })).toHaveAttribute("href", MEMBERSHIP_URL);
  expect(screen.getByText(/legal gambling age/)).toBeInTheDocument();
});
