import React from "react";
import ufcImage from "../assets/2021_to_2024.png";  
const Home = () => {
  return (
    <div className="container mx-auto p-8">
      <div className="bg-gradient-to-r from-blue-500 to-teal-400 rounded-xl shadow-xl overflow-hidden">
        <div className="text-white p-8 text-center">
          <h1 className="text-5xl font-bold mb-4">UFC Fight Predictor</h1>
          <p className="text-xl">
            Revolutionizing UFC Betting with AI
          </p>
        </div>

        <div className="p-8 bg-white rounded-b-xl">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-3xl font-semibold text-gray-800 mb-6">About the Model</h2>
            <p className="mb-6 text-lg text-gray-700 font-sans">
              Consistently averaging 10% ROI over the past year with a robust 64% accuracy, the UFC AI model is at the forefront of sports betting innovation. The best result we have simulated was turning $1000 on February 22, 2022 to $3042.19 by December 16, 2023, which shows what could possibly happen in the long term if the model learns the fighting meta well. Details on <a href="https://github.com/jazyz/UFCFightPredictor" className="text-blue-600 hover:text-blue-800">GitHub</a>.
            </p>

            <div className="mt-10">
              <h3 className="text-2xl font-semibold text-gray-800 mb-4">Using betUFC</h3>
              <div className="grid md:grid-cols-2 gap-6">
                <div className="p-6 border-l-4 border-blue-500 bg-gray-50">
                  <h4 className="text-xl font-semibold mb-2">Predictor</h4>
                  <p className="text-gray-600">
                    Enter two fighters from the same weight class and let our AI work its magic. Up-to-date statistics and sophisticated algorithms come together to predict the outcome, offering you a strategic edge.
                  </p>
                </div>
                <div className="p-6 border-l-4 border-teal-500 bg-gray-50">
                  <h4 className="text-xl font-semibold mb-2">Testing</h4>
                  <p className="text-gray-600">
                    Simulate bets on past events, tracking the AI's performance over time. The graph below is from 2021 to 2024, utilizing a risky Kelly Criterion strategy to place bets.
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-10 flex justify-center">
        <img src={ufcImage} alt="UFC Statistics from 2021 to 2024" className="max-w-full h-auto rounded-lg shadow-lg" />
      </div>
        </div>
        
      </div>

    </div>
  );
};

export default Home;
