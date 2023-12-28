import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import FightPredictor from "./components/FightPredictor";
import About from "./components/About";
import Results from "./components/Results";
import Testing from "./components/Testing";

const App = () => {
  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<FightPredictor />} />
        <Route path="/about" element={<About />} />
        <Route path="/results" element={<Results />} />
        <Route path="/testing" element={<Testing />} />
      </Routes>
    </Router>
  );
};

export default App;
