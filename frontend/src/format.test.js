import { pct, money, signedMoney, signedPct, odds, eventName, shortDate, monthLabel, stdErrPts } from "./format";

test("pct formats fractions and dashes nulls", () => {
  expect(pct(0.6702)).toBe("67.0%");
  expect(pct(0.6702, 0)).toBe("67%");
  expect(pct(null)).toBe("—");
});

test("money and signed helpers", () => {
  expect(money(1132.93)).toBe("$1,132.93");
  expect(signedMoney(-8.5)).toBe("−$8.50");
  expect(signedMoney(12)).toBe("+$12.00");
  expect(signedPct(13.3)).toBe("+13.3%");
  expect(signedPct(-0.4)).toBe("−0.4%");
});

test("odds keeps the plus sign on dogs", () => {
  expect(odds(150)).toBe("+150");
  expect(odds(-210)).toBe("-210");
});

test("eventName turns ufcstats slugs into names", () => {
  expect(eventName("ufc-fight-night-september-06-2025")).toBe("UFC Fight Night");
  expect(eventName("ufc-320")).toBe("UFC 320");
  expect(eventName("ufc-on-espn-70")).toBe("UFC on ESPN 70");
  expect(eventName("start")).toBe("Start");
});

test("dates", () => {
  expect(shortDate("2025-09-06")).toBe("Sep 6, 2025");
  expect(monthLabel("2025-09")).toBe("Sep ’25");
});

test("stdErrPts is the binomial standard error in percentage points", () => {
  expect(stdErrPts(0.67, 282)).toBeCloseTo(2.8, 1);
});
