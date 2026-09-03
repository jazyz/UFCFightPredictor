import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Navbar from "./Navbar";

test("nav links carry the selected window; the picks button does not", () => {
  render(
    <MemoryRouter initialEntries={["/?from=2025-01-01&to=2025-12-31"]}>
      <Navbar />
    </MemoryRouter>
  );
  const results = screen.getAllByRole("link", { name: "Results" });
  results.forEach((a) => expect(a).toHaveAttribute("href", "/results?from=2025-01-01&to=2025-12-31"));
  expect(screen.getByRole("link", { name: "Get the picks" })).toHaveAttribute("href", "/join");
});
