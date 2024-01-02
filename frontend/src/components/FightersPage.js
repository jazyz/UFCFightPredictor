import React, { useState, useEffect } from 'react';
import FightersDropdown from './FightersDropdown'; // Ensure this is the correct path
import axios from 'axios';

const FightersPage = () => {
  const [fighterList, setFighterList] = useState([]);

  useEffect(() => {
    const getFighters = async () => {
      try {
        const response = await axios.get('http://127.0.0.1:5000/get_all_fighter_names');
        setFighterList(response.data); // Assuming the API returns an array of names
      } catch (error) {
        console.error('Failed to fetch fighters:', error);
        // Handle errors here
      }
    };

    getFighters();
  }, []);

  return (
    <div className="fighters-container">
      <h1 className="fighters-header">Select a Fighter</h1>
      <FightersDropdown fighters={fighterList} />
    </div>
  );
};

export default FightersPage;
