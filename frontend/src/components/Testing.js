import { React, useState } from "react";
import axios from "axios";
import { baseURL } from "../constants";

const Testing = () => {
  const [startYear, setStartYear] = useState(null);
  const [endYear, setEndYear] = useState(null);
  const [results, setResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [imageSrc, setImageSrc] = useState("");
  const [selectedRow1, setSelectedRow1] = useState(1);
  const [selectedRow2, setSelectedRow2] = useState(0);
  const row1Buttons = ["Conservative", "Normal", "Risky"];
  const row2Buttons = ["Kelly Criterion", "Flat"];
  const [strategy, setStrategy] = useState([0.05, 0.05, 0]);

  // # conservative strategy: 0.05, 0.05, 0
  // # normal strategy: 0.1, 0.1, 0
  // # risky strategy: 0.2, 0.2, 0
  // # kc strategy: don't do anything
  // # flat strategy: change parameter 3 to 0.01 (if 3rd parameter > 0 then flat all predictions)
  // # conservative flat = 1% of bankroll per bet
  // # normal flat = 1.5% of bankroll per bet
  // # risky flat = 2% of bankroll per bet

  const handleButtonClick = (row, buttonIndex) => {
    // console.log(row, buttonIndex);
    let updatedStrategy = [...strategy];
    if (row === 1) {
      setSelectedRow1(buttonIndex);
      updatedStrategy[0] = [0.025, 0.05, 0.1][buttonIndex];
      if (selectedRow2 === 1) {
        updatedStrategy[2] = 0.005 * buttonIndex + 0.005;
      } else {
        updatedStrategy[2] = 0;
      }
    } else if (row === 2) {
      setSelectedRow2(buttonIndex);
      if (buttonIndex === 1) {
        updatedStrategy[2] = 0.005 * selectedRow1 + 0.005;
      } else {
        updatedStrategy[2] = 0;
      }
    }
    // console.log(updatedStrategy);
    setStrategy([...updatedStrategy]);
    // console.log(strategy);
  };

  const handleTestClick = async () => {
    if (
      ![2021, 2022, 2023, 2024].includes(parseInt(startYear)) ||
      ![2021, 2022, 2023, 2024].includes(parseInt(endYear))
    ) {
      alert(
        "Please enter valid years: 2021, 2022, 2023, or 2024 for both start and end years."
      );
      return;
    }
    if (parseInt(startYear) >= parseInt(endYear)) {
      alert("Start year must be less than end year.");
      return;
    }

    const testFrom = `${startYear}-01-01`;
    const testTo = `${endYear}-01-01`;

    try {
      setIsLoading(true);
      console.log("Predicting fights...");
      const response = await axios.post(
        `${baseURL}/test`,
        {
          testFrom_card: testFrom,
          testTo_card: testTo,
          strategy: strategy,
        },
        {
          timeout: 600000, // 10 minutes
        }
      );
      // console.log(response.data);
      setResults(response.data.content);
      const getImg = await axios.get(`${baseURL}/get_bankroll_plot`);
      setImageSrc(`data:image/png;base64,${getImg.data.image}`);
      // console.log(imageSrc);
      console.log("Done");
      setIsLoading(false);
    } catch (error) {
      setIsLoading(false);
      console.error("Error predicting fight:", error);
    }
  };

  return (
    <div className="bg-white-100 p-4 sm:p-6 lg:p-8 w-full">
      <div className="space-y-8 max-w-3xl mx-auto">
        <h2 className="text-3xl font-bold text-gray-900">
          Testing UFC Predictor
        </h2>
        <p className="text-md">
          Note that testing may take a while, since the model retrains every 6
          months of fights.
        </p>
        <div className="bg-white p-8 shadow-md rounded-lg">
          <h2 className="text-2xl font-semibold mb-4">UFC Fight Predictor</h2>
          <div className="mb-4">
            <input
              className="w-full border rounded py-2 px-3 border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              type="number"
              placeholder="Enter Start Year (2021-2024)"
              value={startYear}
              onChange={(e) => setStartYear(e.target.value)}
            />
          </div>
          <div className="mb-4">
            <input
              className="w-full border rounded py-2 px-3 border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              type="number"
              placeholder="Enter End Year (2021-2024)"
              value={endYear}
              onChange={(e) => setEndYear(e.target.value)}
            />
          </div>
          <button
            className="w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            onClick={handleTestClick}
            disabled={isLoading}
          >
            {isLoading ? "Testing..." : "Start Test"}
          </button>
        </div>
        <div className="bg-white p-8 shadow-md rounded-lg">
          <h2 className="text-2xl font-semibold mb-4">Betting Strategy</h2>
          <div className="flex flex-wrap justify-center mb-4">
            {row1Buttons.map((name, index) => (
              <button
                key={name}
                className={`m-1 px-4 py-2 text-sm font-medium rounded-md ${
                  selectedRow1 === index
                    ? "bg-green-600 text-white"
                    : "bg-green-300 text-green-900 hover:bg-green-400"
                } focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500`}
                onClick={() => handleButtonClick(1, index)}
              >
                {name}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap justify-center">
            {row2Buttons.map((name, index) => (
              <button
                key={name}
                className={`m-1 px-4 py-2 text-sm font-medium rounded-md ${
                  selectedRow2 === index
                    ? "bg-blue-600 text-white"
                    : "bg-blue-300 text-blue-900 hover:bg-blue-400"
                } focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500`}
                onClick={() => handleButtonClick(2, index)}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
        {imageSrc && (
          <div className="mt-4">
            <img
              src={imageSrc}
              alt="Bankroll Plot"
              className="max-w-full h-auto"
            />
          </div>
        )}
        {results && (
          <div className="mt-4">
            <pre className="text-wrap">{results}</pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default Testing;
