import { React, useState } from "react";
import axios from "axios";
import { baseURL } from "../constants";

const Testing = () => {
  const [startYear, setStartYear] = useState(null);
  const [endYear, setEndYear] = useState(null);
  const [results, setResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [imageSrc, setImageSrc] = useState("");
  const [selectedRow1, setSelectedRow1] = useState(null);
  const [selectedRow2, setSelectedRow2] = useState(null);
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
    console.log(row, buttonIndex);
    let updatedStrategy = [...strategy];
    if (row === 1) {
      setSelectedRow1(buttonIndex);
      updatedStrategy[0] = [0.05, 0.1, 0.2][buttonIndex];
      if (selectedRow2 === 1) {
        updatedStrategy[2] = 0.005 * (buttonIndex + 1) + 0.005;
      } else {
        updatedStrategy[2] = 0;
      }
    } else if (row === 2) {
      setSelectedRow2(buttonIndex);
      if (buttonIndex === 1) {
        updatedStrategy[2] = 0.005 * (selectedRow1 + 1) + 0.005;
      } else {
        updatedStrategy[2] = 0;
      }
    }
    console.log(updatedStrategy);
    setStrategy([...updatedStrategy]);
    console.log(strategy);
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
      const response = await axios.post(`${baseURL}/test`, {
        testFrom_card: testFrom,
        testTo_card: testTo,
        strategy: strategy,
      });
      console.log(response.data);
      setResults(response.data.content);
      const getImg = await axios.get(`${baseURL}/get_bankroll_plot`);
      setImageSrc(`data:image/png;base64,${getImg.data.image}`);
      console.log(imageSrc);
      setIsLoading(false);
    } catch (error) {
      setIsLoading(false);
      console.error("Error predicting fight:", error);
    }
  };

  return (
    <div className="container mx-auto mt-8">
      <h2 className="text-2xl font-semibold mb-4">Testing UFC Predictor</h2>
      <div className="flex row">
        <div className="bg-white p-8 shadow-md rounded-lg w-96 mr-8">
          <h2 className="text-2xl font-semibold mb-4">UFC Fight Predictor</h2>
          <div className="mb-4">
            <input
              className="w-full border rounded py-2 px-3"
              type="number"
              placeholder="Enter Start Year (2021-2024)"
              value={startYear}
              onChange={(e) => setStartYear(e.target.value)}
            />
          </div>
          <div className="mb-4">
            <input
              className="w-full border rounded py-2 px-3"
              type="number"
              placeholder="Enter End Year (2021-2024)"
              value={endYear}
              onChange={(e) => setEndYear(e.target.value)}
            />
          </div>
          <button
            className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
            onClick={handleTestClick}
          >
            {isLoading ? "Gathering Data..." : "Predict"}
          </button>
        </div>
        <div className="bg-white p-8 shadow-md rounded-lg w-96">
          <h2 className="text-2xl font-semibold mb-4">Betting Strategy</h2>

          {/* Row 1 Buttons */}
          <div className="mb-4">
            {row1Buttons.map((name, index) => (
              <button
                key={index}
                className={`mr-2 p-2 border ${
                  selectedRow1 === index ? "bg-blue-500 text-white" : "bg-white"
                }`}
                onClick={() => handleButtonClick(1, index)}
              >
                {name}
              </button>
            ))}
          </div>

          {/* Row 2 Buttons */}
          <div>
            {row2Buttons.map((name, index) => (
              <button
                key={index}
                className={`mr-2 p-2 border ${
                  selectedRow2 === index ? "bg-blue-500 text-white" : "bg-white"
                }`}
                onClick={() => handleButtonClick(2, index)}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
      </div>
      {imageSrc && (
        <div className="mt-4 space-x-4">
          <img src={imageSrc} alt="Bankroll Plot" />
        </div>
      )}
      <div className="mt-4 space-x-4">
        <pre className="text-wrap">{results}</pre>
      </div>
    </div>
  );
};

export default Testing;
