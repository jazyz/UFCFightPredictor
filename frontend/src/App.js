// App.js
import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./components/Home";
import FightPredictor from "./components/FightPredictor";
import About from "./components/About";
import Bets from "./components/Bets";
import Testing from "./components/Testing";
import axios from "axios";
import { baseURL } from "./constants";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const App = () => {
  const [nameOptions, setNameOptions] = useState([""]);

  // fetch all fighter names from backend
  useEffect(() => {
    axios
      .get(`${baseURL}/get_all_fighter_names`)
      .then((res) => {
        setNameOptions(res.data);
      })
      .catch((err) => {
        console.error(err);
        toast.error("Error fetching fighter names.");
      });
  }, []);

  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        {/* <Route path="/about" element={<About />} /> */}
        <Route
          path="/predict"
          element={<FightPredictor nameOptions={nameOptions} />}
        />
        <Route path="/bets" element={<Bets />} />
        <Route path="/testing" element={<Testing />} />
      </Routes>
      <ToastContainer />
    </Router>
  );
};

export default App;
