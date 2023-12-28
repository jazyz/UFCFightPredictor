import { React, useState } from "react";
import raw from "../constants/predictions.txt";

const Results = () => {
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
        Results from UFC Predictor
      </h2>
      <pre className="text-wrap">{results}</pre>
    </div>
  );
};

export default Results;
