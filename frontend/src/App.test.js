import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the brand and the membership button", () => {
  render(<App />);
  expect(screen.getByText("UFC Alpha")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Get the picks" })).toHaveAttribute("target", "_blank");
});
