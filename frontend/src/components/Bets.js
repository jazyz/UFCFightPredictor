import React, { useEffect, useState } from "react";
import axios from "axios";
import raw from "../constants/predictions.txt";
import { baseURL } from "../constants";

const Bets = () => {
  const [results, setResults] = useState(null);
  const [imageSrc, setImageSrc] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const getImg = await axios.get(`${baseURL}/get_predictions_plot`);
        setImageSrc(`data:image/png;base64,${getImg.data.image}`);

        const response = await fetch(raw);
        const text = await response.text();
        setResults(text);
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="bg-white-100 p-4 sm:p-6 lg:p-8 w-full">
      <div className="space-y-8 max-w-3xl mx-auto">
        <h2 className="text-3xl font-bold text-gray-900">
          Bets from UFC Predictor
        </h2>
        <p className="text-md mb-4">
          Paper bets placed starting from September 16, 2023.
        </p>
        {imageSrc && (
          <div className="mt-4">
            <img
              src={imageSrc}
              alt="Bankroll Plot"
              className="max-w-full h-auto"
            />
          </div>
        )}
        <pre className="text-wrap">{results}</pre>
      </div>
    </div>
  );
};

export default Bets;
