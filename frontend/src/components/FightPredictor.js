import React, { useState, useEffect } from "react";
import axios from "axios";
import { baseURL } from "../constants";
import { toast } from "react-toastify";

const FightPredictor = ({ nameOptions }) => {
  const [fighterName1, setFighterName1] = useState("");
  const [fighterName2, setFighterName2] = useState("");
  const [fighter1_stats, setFighter1_stats] = useState(null);
  const [fighter2_stats, setFighter2_stats] = useState(null);
  const [predictedData, setPredictedData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showExtraStats, setShowExtraStats] = useState(false);

  const calculateAge = (dob) => {
    const birthDate = new Date(dob);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const m = today.getMonth() - birthDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    return age;
  };

  const toggleExtraStats = () => {
    setShowExtraStats(!showExtraStats);
  };

  const handlePredictClick = async () => {
    try {
      if (!nameOptions.includes(fighterName1)) {
        throw new Error("Please enter valid fighter names.");
      }
      if (!nameOptions.includes(fighterName2)) {
        throw new Error("Please enter valid fighter names.");
      }
      if (fighterName1 === fighterName2) {
        throw new Error("Please enter two different fighter names.");
      }

      setIsLoading(true);
      console.log("Predicting fight...");
      const response = await axios.post(`${baseURL}/predict`, {
        fighter_name1: fighterName1,
        fighter_name2: fighterName2,
      });
      console.log(response.data.message);
      const training = await axios.post(`${baseURL}/train`);
      console.log(training.data.message);
      const fighterStats = await axios.post(`${baseURL}/get_stats`, {
        fighter_name1: fighterName1,
        fighter_name2: fighterName2,
      });
      console.log(fighterStats.data);
      setFighter1_stats(fighterStats.data.fighter1_stats);
      setFighter2_stats(fighterStats.data.fighter2_stats);
      const results = await axios.get(`${baseURL}/get_predicted_data`);
      console.log(results.data);
      setPredictedData(results.data.predicted_data);
      setIsLoading(false);
    } catch (error) {
      toast.error(error.message);
      setIsLoading(false);
      console.error("Error predicting fight:", error);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white-100 px-4 sm:px-6 lg:px-8">
      <div className="bg-white p-6 shadow-lg rounded-lg max-w-md w-full space-y-8">
        <h2 className="text-center text-3xl font-bold text-gray-900">
          UFC Fight Predictor
        </h2>
        <form className="mt-8 space-y-6" action="#" method="POST">
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <label htmlFor="fighter-1" className="sr-only">
                Fighter 1 Name
              </label>
              <input
                id="fighter-1"
                name="fighter-1"
                type="text"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Enter Fighter 1 Name"
                value={fighterName1}
                onChange={(e) => setFighterName1(e.target.value)}
                list="options-1"
              />
              <datalist id="options-1">
                {nameOptions.map((option, index) => (
                  <option key={`option-1-${index}`} value={option} />
                ))}
              </datalist>
            </div>
            <div>
              <label htmlFor="fighter-2" className="sr-only">
                Fighter 2 Name
              </label>
              <input
                id="fighter-2"
                name="fighter-2"
                type="text"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Enter Fighter 2 Name"
                value={fighterName2}
                onChange={(e) => setFighterName2(e.target.value)}
                list="options-2"
              />
              <datalist id="options-2">
                {nameOptions.map((option, index) => (
                  <option key={`option-2-${index}`} value={option} />
                ))}
              </datalist>
            </div>
          </div>
          <div>
            <button
              type="button"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              onClick={handlePredictClick}
              disabled={isLoading}
            >
              {isLoading ? "Gathering Data..." : "Predict"}
            </button>
          </div>
        </form>
        {predictedData && (
          <div className="mt-4 p-4 bg-blue-100 rounded-md">
            <h3 className="text-lg font-semibold text-center">
              Prediction Results
            </h3>
            <div className="flex justify-between items-center">
              <div className="p-2">
                <h4 className="text-md font-bold">{fighter1_stats.Fighter}</h4>
                <p>Age: {fighter1_stats && calculateAge(fighter1_stats.dob)}</p>
                <p>ELO: {parseFloat(fighter1_stats.elo).toFixed(2)}</p>
                <p>
                  Probability to Win:{" "}
                  {(
                    (100 *
                      (predictedData[0].probability_win +
                        predictedData[1].probability_loss)) /
                    2
                  ).toFixed(2)}
                  %
                </p>
              </div>
              <div className="p-2">
                <h4 className="text-md font-bold">{fighter2_stats.Fighter}</h4>
                <p>Age: {fighter2_stats && calculateAge(fighter2_stats.dob)}</p>
                <p>ELO: {parseFloat(fighter2_stats.elo).toFixed(2)}</p>
                <p>
                  Probability to Win:{" "}
                  {(
                    (100 *
                      (predictedData[1].probability_win +
                        predictedData[0].probability_loss)) /
                    2
                  ).toFixed(2)}
                  %
                </p>
              </div>
            </div>
          </div>
        )}
        <button
          className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          onClick={toggleExtraStats}
        >
          {showExtraStats ? "Hide Extra Stats" : "Show Extra Stats"}
        </button>
        {showExtraStats && fighter1_stats && fighter2_stats && (
          <div className="mt-4 p-4 bg-gray-200 rounded-md">
            <h3 className="text-lg font-semibold text-center">Extra Stats</h3>
            <div className="flex justify-between items-center">
              <div className="p-2">
                <h4 className="text-md font-bold">{fighter1_stats.Fighter}</h4>
                <p>Win Streak: {fighter1_stats.winstreak}</p>
                <p>Loss Streak: {fighter1_stats.losestreak}</p>
                <p>
                  Avg Opponent Elo:{" "}
                  {(
                    parseFloat(fighter1_stats.oppelo) /
                    parseFloat(fighter1_stats.totalfights)
                  ).toFixed(2)}
                </p>
                <p>Title Wins: {fighter1_stats.titlewins}</p>
              </div>
              <div className="p-2">
                <h4 className="text-md font-bold">{fighter2_stats.Fighter}</h4>
                <p>Win Streak: {fighter2_stats.winstreak}</p>
                <p>Loss Streak: {fighter2_stats.losestreak}</p>
                <p>
                  Avg Opponent Elo:{" "}
                  {(
                    parseFloat(fighter2_stats.oppelo) /
                    parseFloat(fighter2_stats.totalfights)
                  ).toFixed(2)}
                </p>
                <p>Title Wins: {fighter2_stats.titlewins}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FightPredictor;
