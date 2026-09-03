import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, useSearchParams } from "react-router-dom";
import PeriodFilter from "./PeriodFilter";

const range = { start: "2024-01-01", end: "2026-08-30", retrains: ["2024-01-01", "2024-07-13", "2025-01-11", "2025-07-12", "2026-01-24", "2026-07-25"] };

function Probe() {
  const [params] = useSearchParams();
  return <span data-testid="query">{params.toString()}</span>;
}

test("presets write the window to the URL and mark the active one", () => {
  render(
    <MemoryRouter>
      <PeriodFilter range={range} window={{ start: range.start, end: range.end }} />
      <Probe />
    </MemoryRouter>
  );
  expect(screen.getByRole("button", { name: "All time" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "2025" }));
  expect(screen.getByTestId("query")).toHaveTextContent("from=2025-01-01&to=2025-12-31");
});

test("choosing All time clears the query", () => {
  render(
    <MemoryRouter initialEntries={["/results?from=2025-01-01&to=2025-12-31"]}>
      <PeriodFilter range={range} window={{ start: "2025-01-01", end: "2025-12-31" }} />
      <Probe />
    </MemoryRouter>
  );
  expect(screen.getByRole("button", { name: "2025" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "All time" }));
  expect(screen.getByTestId("query")).toHaveTextContent("");
});
