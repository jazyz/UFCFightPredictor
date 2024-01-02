// App.js
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import FightPredictor from './components/FightPredictor';
import About from './components/About';
import Results from './components/Results';
import Testing from './components/Testing';
import FightersPage from './components/FightersPage'; // Import the FightersPage
import axios from 'axios';
import { baseURL } from './constants';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

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
        <Route path="/" element={<FightPredictor nameOptions={nameOptions} />} />
        <Route path="/about" element={<About />} />
        <Route path="/results" element={<Results />} />
        <Route path="/testing" element={<Testing />} />
      </Routes>
      <ToastContainer />
    </Router>
  );
};

export default App;
