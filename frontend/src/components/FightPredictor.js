import React, { useState } from "react";
import axios from "axios";

const FightPredictor = () => {
  const [fighterName1, setFighterName1] = useState("");
  const [fighterName2, setFighterName2] = useState("");
  const [stats, setStats] = useState(null);
  const [predictedData, setPredictedData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const baseURL = "http://127.0.0.1:5000/";

  const handlePredictClick = async () => {
    try {
      setIsLoading(true);
      console.log("Predicting fight...");
      const response = await axios.post(`${baseURL}/predict`, {
        fighter_name1: fighterName1,
        fighter_name2: fighterName2,
      });
      console.log(response.data.message);
      const training = await axios.post(`${baseURL}/train`);
      console.log(training.data.message);
      const fighterStats = await axios.get(`${baseURL}/get_stats`);
      setStats(fighterStats.data.stats[0]);
      console.log(stats);
      const results = await axios.get(`${baseURL}/get_predicted_data`);
      setPredictedData(results.data.predicted_data[0]);
      console.log(results.data.predicted_data);
      setIsLoading(false);
    } catch (error) {
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
            type="text"
            placeholder="Enter Fighter 1 Name"
            value={fighterName1}
            onChange={(e) => setFighterName1(e.target.value)}
          />
        </div>
        <div className="mb-4">
          <input
            className="w-full border rounded py-2 px-3"
            type="text"
            placeholder="Enter Fighter 2 Name"
            value={fighterName2}
            onChange={(e) => setFighterName2(e.target.value)}
          />
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
                  {stats.fighter_name}
                </h3>
                <p>{stats.fighter_record}</p>
                <p>{stats.fighter_dob}</p>
                <p>{stats.fighter_height}</p>
                <p>{stats.fighter_reach}</p>
              </div>
              <div className="flex flex-col">
                <h3 className="text-xl font-semibold mb-2">
                  {stats.opponent_name}
                </h3>
                <p>{stats.opponent_record}</p>
                <p>{stats.opponent_dob}</p>
                <p>{stats.opponent_height}</p>
                <p>{stats.opponent_reach}</p>
              </div>
            </div>
            <div className="mt-4">
              <p>
                Probability Win: {predictedData.probability_win.toFixed(2)}%
              </p>
              <p>
                Probability Lose: {predictedData.probability_loss.toFixed(2)}%
              </p>
              <p>
                {stats.fighter_name}{" "}
                {predictedData.predicted_result === "win"
                  ? "defeats"
                  : "loses to"}{" "}
                {stats.opponent_name}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FightPredictor;
