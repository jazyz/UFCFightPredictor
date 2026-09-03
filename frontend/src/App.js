import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";
import Home from "./components/Home";
import Results from "./components/Results";
import Bets from "./components/Bets";
import backtest from "./data/backtest.json";
import ledger from "./data/ledger.json";

const App = () => (
  <Router>
    <ScrollToTop />
    <div className="min-h-screen bg-ground font-body text-ink">
      <Navbar />
      <Routes>
        <Route path="/" element={<Home data={backtest} ledger={ledger} />} />
        <Route path="/results" element={<Results data={backtest} />} />
        <Route path="/bets" element={<Bets data={backtest} ledger={ledger} />} />
      </Routes>
      <Footer />
    </div>
  </Router>
);

export default App;
