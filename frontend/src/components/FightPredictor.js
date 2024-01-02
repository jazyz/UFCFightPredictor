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
  const [showAdvancedStats, setShowAdvancedStats] = useState(false);

  const toggleAdvancedStats = () => {
    setShowAdvancedStats(!showAdvancedStats);
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
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 shadow-md rounded-lg w-96">
        <h2 className="text-2xl font-semibold mb-4">UFC Fight Predictor</h2>
        <div className="mb-4">
          <input
            className="w-full border rounded py-2 px-3"
            list="options-1"
            type="text"
            placeholder="Enter Fighter 1 Name"
            value={fighterName1}
            onChange={(e) => setFighterName1(e.target.value)}
          />
          <datalist id="options-1">
            {nameOptions.map((option) => (
              <option key={`${option}-1`} value={option} />
            ))}
          </datalist>
        </div>
        <div className="mb-4">
          <input
            className="w-full border rounded py-2 px-3"
            list="options-2"
            type="text"
            placeholder="Enter Fighter 2 Name"
            value={fighterName2}
            onChange={(e) => setFighterName2(e.target.value)}
          />
          <datalist id="options-2">
            {nameOptions.map((option) => (
              <option key={`${option}-2`} value={option} />
            ))}
          </datalist>
        </div>
        <button
          className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
          onClick={handlePredictClick}
        >
          {isLoading ? "Gathering Data..." : "Predict"}
        </button>
        {predictedData && (
          <div className="mt-4 space-x-4">
            <div className="flex space-x-4">
              <div className="flex flex-col">
                <h3 className="text-xl font-semibold mb-2">
                  {fighter1_stats.Fighter}
                </h3>
                <p>Age: {fighter1_stats.dob}</p>
                <p>ELO: {parseFloat(fighter1_stats.elo).toFixed(2)}</p>
              </div>
              <div className="flex flex-col">
                <h3 className="text-xl font-semibold mb-2">
                  {fighter2_stats.Fighter}
                </h3>
                <p>Age: {fighter2_stats.dob}</p>
                <p>ELO: {parseFloat(fighter2_stats.elo).toFixed(2)}</p>
              </div>
            </div>
            <div className="mt-4">
              <p>
                Probability Win:{" "}
                {(
                  (100 *
                    (predictedData[0].probability_win +
                      predictedData[1].probability_loss)) /
                  2
                ).toFixed(2)}
                %
              </p>
              <p>
                Probability Lose:{" "}
                {(
                  (100 *
                    (predictedData[1].probability_win +
                      predictedData[0].probability_loss)) /
                  2
                ).toFixed(2)}
                %
              </p>
              <p>
                {fighter1_stats.Fighter}{" "}
                {(
                  (100 *
                    (predictedData[0].probability_win +
                      predictedData[1].probability_loss)) /
                  2
                ).toFixed(2) > 50
                  ? "defeats"
                  : "loses to"}{" "}
                {fighter2_stats.Fighter}
              </p>
            </div>
          </div>
        )}

        {/* New: Advanced Stats Button */}
        <button
          className="w-full mt-4 bg-gray-500 text-white py-2 rounded hover:bg-gray-600"
          onClick={toggleAdvancedStats}
        >
          {showAdvancedStats ? "Hide Advanced Stats" : "Show Advanced Stats"}
        </button>

        {/* New: Advanced Stats Box */}
        {showAdvancedStats && fighter1_stats && fighter2_stats && (
          <div className="mt-4 space-x-4">
            <div className="flex space-x-4">
              <div className="flex flex-col">
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
              <div className="flex flex-col">
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
