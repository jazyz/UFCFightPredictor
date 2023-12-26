import { React, useState } from "react";
import axios from "axios";
import raw from "../constants/predictions.txt";

const Testing = () => {
  const [testFrom, setTestFrom] = useState(null);
  const [testTo, setTestTo] = useState(null);
  const [results, setResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const baseURL = "http://127.0.0.1:5000/";

  const handleTestClick = async () => {
    try {
      setIsLoading(true);
      console.log("Predicting fights...");
      const response = await axios.post(`${baseURL}/test`, {
        testFrom_card: testFrom,
        testTo_card: testTo,
      });
      console.log(response.data);
      setResults(response.data.content);
      setIsLoading(false);
    } catch (error) {
      setIsLoading(false);

      console.error("Error predicting fight:", error);
    }
  };

  return (
    <div className="container mx-auto mt-8">
      <h2 className="text-2xl font-semibold mb-4">Testing UFC Predictor</h2>
      <div className="bg-white p-8 shadow-md rounded-lg w-96">
        <h2 className="text-2xl font-semibold mb-4">UFC Fight Predictor</h2>
        <div className="mb-4">
          <input
            className="w-full border rounded py-2 px-3"
            type="text"
            placeholder="Enter Testing From Date Fight Card Link"
            value={testFrom}
            onChange={(e) => setTestFrom(e.target.value)}
          />
        </div>
        <div className="mb-4">
          <input
            className="w-full border rounded py-2 px-3"
            type="text"
            placeholder="Enter Testing To Date Fight Card Link"
            value={testTo}
            onChange={(e) => setTestTo(e.target.value)}
          />
        </div>
        <button
          className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
          onClick={handleTestClick}
        >
          {isLoading ? "Gathering Data..." : "Predict"}
        </button>
      </div>
      <div className="mt-4 space-x-4">
        <pre className="text-wrap">{results}</pre>
      </div>
    </div>
  );
};

export default Testing;
