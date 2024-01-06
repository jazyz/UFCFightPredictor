import { React, useState } from "react";
import raw from "../constants/predictions.txt";

const Bets = () => {
  let predictions = [];
  const [results, setResults] = useState(null);
  fetch(raw)
    .then((r) => r.text())
    .then((text) => {
      console.log("text decoded:", text);
      setResults(text);
      //   predictions = text.split("\n");
      //   console.log("predictions:", predictions);
    });
  return (
    <div className="container mx-auto mt-8">
      <h2 className="text-2xl font-semibold mb-4">
        Bets from UFC Predictor
      </h2>
      <p className="text-md mb-4">Paper bets placed starting from September 16, 2023.</p>
      <pre className="text-wrap">{results}</pre>
    </div>
  );
};

export default Bets;
