import React, { useMemo } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";
import PeriodFilter from "./components/PeriodFilter";
import Home from "./components/Home";
import Results from "./components/Results";
import Bets from "./components/Bets";
import Methodology from "./components/Methodology";
import Join from "./components/Join";
import backtest from "./data/backtest.json";
import ledger from "./data/ledger.json";
import { aggregate, clampWindow, windowRetrains } from "./aggregate";

/** The page data for one window: the summary sections plus window, range and config. */
function viewFor(start, end) {
  return {
    generated: backtest.generated,
    range: backtest.range,
    config: backtest.config,
    window: { start, end, retrains: windowRetrains(backtest.range, start, end) },
    ...aggregate(backtest.fights, start, end, backtest.config),
  };
}

const DEFAULT_VIEW = viewFor(backtest.default_window.start, backtest.default_window.end);

function Site() {
  const [params] = useSearchParams();
  const { start, end } = clampWindow(backtest.range, params.get("from"), params.get("to"), backtest.default_window);
  const view = useMemo(() => viewFor(start, end), [start, end]);
  const filter = <PeriodFilter range={backtest.range} window={view.window} />;
  return (
    <div className="min-h-screen bg-ground font-body text-ink">
      <Navbar />
      <Routes>
        <Route path="/" element={<>{filter}<Home data={view} /></>} />
        <Route path="/results" element={<>{filter}<Results data={view} /></>} />
        <Route path="/bets" element={<>{filter}<Bets data={view} ledger={ledger} /></>} />
        <Route path="/methodology" element={<Methodology data={DEFAULT_VIEW} />} />
        <Route path="/join" element={<Join data={DEFAULT_VIEW} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Footer />
    </div>
  );
}

const App = () => (
  <Router>
    <ScrollToTop />
    <Site />
  </Router>
);

export default App;
