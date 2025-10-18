import React, { useState } from "react";
import axios from "axios";
import { baseURL } from "../constants";
import { toast } from "react-toastify";

const EventPredictor = () => {
  const [eventUrl, setEventUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [eventData, setEventData] = useState(null);
  const [error, setError] = useState(null);
  const [bankroll, setBankroll] = useState(1000);
  const [customOdds, setCustomOdds] = useState({}); // {fightIndex: {red: odds, blue: odds}}
  const [kellyFraction, setKellyFraction] = useState(0.05); // Default 5% (normal strategy)
  const [maxFraction, setMaxFraction] = useState(0.05); // Max 5% per bet

  const handlePredict = async () => {
    if (!eventUrl.trim()) {
      toast.error("Please enter a UFC event URL");
      return;
    }

    // Validate URL format
    if (!eventUrl.includes("ufcstats.com/event-details/")) {
      toast.error("Please enter a valid UFCStats.com event URL");
      return;
    }

    setLoading(true);
    setError(null);
    setEventData(null);

    try {
      const response = await axios.post(`${baseURL}/predict_event`, {
        event_url: eventUrl,
      });

      setEventData(response.data);
      // Initialize custom odds with scraped odds if available
      const initialOdds = {};
      response.data.predictions.forEach((pred, idx) => {
        const matchupKey = `${pred.red_fighter} vs ${pred.blue_fighter}`;
        const odds = response.data.odds?.[matchupKey];
        if (odds) {
          initialOdds[idx] = {
            red: odds.red_odds || "",
            blue: odds.blue_odds || ""
          };
        }
      });
      setCustomOdds(initialOdds);
      toast.success("Predictions generated successfully!");
    } catch (err) {
      const errorMsg = err.response?.data?.error || "Failed to generate predictions";
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const calculateKellyBet = (winProb, odds, bankrollAmount, kellyMultiplier, maxCap) => {
    if (!odds || odds === 0 || !winProb) return null;
    
    // Convert American odds to decimal
    const decimalOdds = odds > 0 ? (odds / 100) + 1 : (100 / Math.abs(odds)) + 1;
    
    // Kelly Criterion: f = (bp - q) / b
    // where b = decimal odds - 1, p = win probability, q = 1 - p
    const b = decimalOdds - 1;
    const p = winProb;
    const q = 1 - p;
    const kelly = (b * p - q) / b;
    
    if (kelly <= 0) return null; // No bet if Kelly is negative
    
    // Apply fractional Kelly (e.g., 5% of Kelly): bet = bankroll * fraction * kelly
    let betAmount = bankrollAmount * kellyMultiplier * kelly;
    
    // Cap at max fraction of bankroll
    const maxBet = bankrollAmount * maxCap;
    betAmount = Math.min(betAmount, maxBet);
    
    // Calculate edge
    const impliedProb = odds > 0 ? 100 / (odds + 100) : Math.abs(odds) / (Math.abs(odds) + 100);
    const edge = p - impliedProb;
    
    return {
      rawKelly: kelly,
      fraction: betAmount / bankrollAmount,
      amount: betAmount,
      edge: edge
    };
  };

  const handleOddsChange = (fightIndex, fighter, value) => {
    setCustomOdds(prev => ({
      ...prev,
      [fightIndex]: {
        ...prev[fightIndex],
        [fighter]: value
      }
    }));
  };

  const getBettingRecommendation = (prediction, odds) => {
    if (!odds) return null;

    const redOdds = odds.red_odds;
    const blueOdds = odds.blue_odds;
    
    if (!redOdds || !blueOdds) return null;

    // Calculate implied probability from odds
    const redImplied = redOdds > 0 ? 100 / (redOdds + 100) : Math.abs(redOdds) / (Math.abs(redOdds) + 100);
    const blueImplied = blueOdds > 0 ? 100 / (blueOdds + 100) : Math.abs(blueOdds) / (Math.abs(blueOdds) + 100);

    // Check if model probability exceeds market probability (value bet)
    const redEdge = prediction.red_win_prob - redImplied;
    const blueEdge = prediction.blue_win_prob - blueImplied;

    const minEdge = 0.05; // Minimum 5% edge to recommend bet

    if (redEdge > minEdge) {
      const kelly = calculateKellyBet(prediction.red_win_prob, redOdds);
      return {
        fighter: prediction.red_fighter,
        edge: redEdge,
        kelly: kelly,
        odds: redOdds,
        probability: prediction.red_win_prob
      };
    } else if (blueEdge > minEdge) {
      const kelly = calculateKellyBet(prediction.blue_win_prob, blueOdds);
      return {
        fighter: prediction.blue_fighter,
        edge: blueEdge,
        kelly: kelly,
        odds: blueOdds,
        probability: prediction.blue_win_prob
      };
    }

    return null;
  };

  const formatOdds = (odds) => {
    if (!odds) return "N/A";
    return odds > 0 ? `+${odds}` : odds.toString();
  };

  const groupFights = (predictions) => {
    // Group predictions by unique matchup
    const grouped = {};
    predictions.forEach(pred => {
      const key = [pred.red_fighter, pred.blue_fighter].sort().join(" vs ");
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(pred);
    });
    
    // Return only one prediction per matchup (the one where predicted winner matches red fighter)
    return Object.values(grouped).map(group => {
      // Find the prediction where red_fighter is favored
      const favored = group.find(p => 
        (p.predicted_winner === "win" && p.red_win_prob > p.blue_win_prob) ||
        (p.predicted_winner === "loss" && p.blue_win_prob > p.red_win_prob)
      );
      return favored || group[0];
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            UFC Event Predictor
          </h1>
          <p className="text-gray-600 mb-6">
            Enter a UFC event URL from ufcstats.com to get predictions for all fights
          </p>

          <div className="flex gap-4 mb-4">
            <input
              type="text"
              value={eventUrl}
              onChange={(e) => setEventUrl(e.target.value)}
              placeholder="http://ufcstats.com/event-details/..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              onClick={handlePredict}
              disabled={loading}
              className="px-8 py-3 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Loading..." : "Predict Event"}
            </button>
          </div>

          <p className="text-sm text-gray-500">
            Example: http://ufcstats.com/event-details/38e5d9dcb0fddc42
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8">
            <p className="text-red-800 font-medium">{error}</p>
          </div>
        )}

        {eventData && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                {eventData.event_name}
              </h2>
              <p className="text-gray-600 mb-4">
                {groupFights(eventData.predictions).length} fights predicted
              </p>
              
              {/* Betting Settings */}
              <div className="mt-4 pt-4 border-t border-gray-200">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Betting Settings</h3>
                
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {/* Bankroll */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Bankroll ($)
                    </label>
                    <input
                      type="number"
                      value={bankroll}
                      onChange={(e) => setBankroll(Number(e.target.value))}
                      placeholder="1000"
                      min="0"
                      step="100"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                    />
                  </div>
                  
                  {/* Kelly Fraction */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Kelly Fraction (%)
                    </label>
                    <input
                      type="number"
                      value={kellyFraction * 100}
                      onChange={(e) => setKellyFraction(Number(e.target.value) / 100)}
                      placeholder="5"
                      min="1"
                      max="100"
                      step="1"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                    />
                  </div>
                  
                  {/* Max Bet Cap */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Max Bet Cap (%)
                    </label>
                    <input
                      type="number"
                      value={maxFraction * 100}
                      onChange={(e) => setMaxFraction(Number(e.target.value) / 100)}
                      placeholder="5"
                      min="1"
                      max="25"
                      step="1"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                    />
                  </div>
                </div>
                
                <div className="mt-3 space-y-2">
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setKellyFraction(0.025); setMaxFraction(0.025); }}
                      className={`px-3 py-1 text-xs rounded-md font-medium ${kellyFraction === 0.025 ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
                    >
                      Conservative (2.5%)
                    </button>
                    <button
                      onClick={() => { setKellyFraction(0.05); setMaxFraction(0.05); }}
                      className={`px-3 py-1 text-xs rounded-md font-medium ${kellyFraction === 0.05 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
                    >
                      Normal (5%)
                    </button>
                    <button
                      onClick={() => { setKellyFraction(0.1); setMaxFraction(0.1); }}
                      className={`px-3 py-1 text-xs rounded-md font-medium ${kellyFraction === 0.1 ? 'bg-red-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
                    >
                      Risky (10%)
                    </button>
                  </div>
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-xs text-blue-700">
                      <span className="font-semibold">Formula:</span> Bet = Bankroll × {(kellyFraction * 100).toFixed(1)}% × Raw Kelly %, capped at {(maxFraction * 100).toFixed(0)}% of bankroll
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Predictions Grid */}
            <div className="grid gap-6 md:grid-cols-2">
              {groupFights(eventData.predictions).map((prediction, idx) => {
                // Get custom odds or default to empty
                const redOdds = customOdds[idx]?.red ? Number(customOdds[idx].red) : null;
                const blueOdds = customOdds[idx]?.blue ? Number(customOdds[idx].blue) : null;
                
                // Calculate Kelly for both fighters with fractional Kelly
                const redKelly = redOdds ? calculateKellyBet(prediction.red_win_prob, redOdds, bankroll, kellyFraction, maxFraction) : null;
                const blueKelly = blueOdds ? calculateKellyBet(prediction.blue_win_prob, blueOdds, bankroll, kellyFraction, maxFraction) : null;
                
                // Determine which bet has more edge (if any)
                const minEdge = 0.05; // 5% minimum edge
                let bestBet = null;
                if (redKelly && redKelly.edge > minEdge && redKelly.fraction > 0) {
                  if (!bestBet || redKelly.edge > bestBet.edge) {
                    bestBet = { ...redKelly, fighter: prediction.red_fighter, odds: redOdds };
                  }
                }
                if (blueKelly && blueKelly.edge > minEdge && blueKelly.fraction > 0) {
                  if (!bestBet || blueKelly.edge > bestBet.edge) {
                    bestBet = { ...blueKelly, fighter: prediction.blue_fighter, odds: blueOdds };
                  }
                }

                return (
                  <div
                    key={idx}
                    className="bg-white rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition-shadow"
                  >
                    <div className="bg-gradient-to-r from-red-600 to-red-700 p-4">
                      <h3 className="text-white font-bold text-lg text-center">
                        {prediction.red_fighter} vs {prediction.blue_fighter}
                      </h3>
                    </div>

                    <div className="p-6">
                      {/* Red Fighter */}
                      <div className="mb-4">
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-semibold text-gray-900">
                            {prediction.red_fighter}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">Odds:</span>
                            <input
                              type="number"
                              value={customOdds[idx]?.red || ""}
                              onChange={(e) => handleOddsChange(idx, "red", e.target.value)}
                              placeholder="-150"
                              className="w-20 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-red-500 focus:border-transparent"
                            />
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-6 relative overflow-hidden">
                          <div
                            className="bg-red-600 h-full rounded-full flex items-center justify-end pr-2"
                            style={{ width: `${prediction.red_win_prob * 100}%` }}
                          >
                            <span className="text-white text-sm font-bold">
                              {(prediction.red_win_prob * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                        {redKelly && redKelly.edge > 0 && (
                          <p className="text-xs text-gray-600 mt-1">
                            Edge: {(redKelly.edge * 100).toFixed(1)}% | Raw Kelly: {(redKelly.rawKelly * 100).toFixed(1)}% | Bet: ${redKelly.amount.toFixed(2)}
                          </p>
                        )}
                      </div>

                      {/* Blue Fighter */}
                      <div className="mb-4">
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-semibold text-gray-900">
                            {prediction.blue_fighter}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">Odds:</span>
                            <input
                              type="number"
                              value={customOdds[idx]?.blue || ""}
                              onChange={(e) => handleOddsChange(idx, "blue", e.target.value)}
                              placeholder="+130"
                              className="w-20 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent"
                            />
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-6 relative overflow-hidden">
                          <div
                            className="bg-blue-600 h-full rounded-full flex items-center justify-end pr-2"
                            style={{ width: `${prediction.blue_win_prob * 100}%` }}
                          >
                            <span className="text-white text-sm font-bold">
                              {(prediction.blue_win_prob * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                        {blueKelly && blueKelly.edge > 0 && (
                          <p className="text-xs text-gray-600 mt-1">
                            Edge: {(blueKelly.edge * 100).toFixed(1)}% | Raw Kelly: {(blueKelly.rawKelly * 100).toFixed(1)}% | Bet: ${blueKelly.amount.toFixed(2)}
                          </p>
                        )}
                      </div>

                      {/* Betting Recommendation */}
                      {bestBet && (
                        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                          <p className="text-green-800 font-bold mb-2">
                            💰 Value Bet Detected
                          </p>
                          <p className="text-sm text-green-700 mb-1">
                            <span className="font-semibold">Bet on:</span> {bestBet.fighter} ({formatOdds(bestBet.odds)})
                          </p>
                          <p className="text-sm text-green-700 mb-1">
                            <span className="font-semibold">Edge:</span> {(bestBet.edge * 100).toFixed(1)}%
                          </p>
                          <p className="text-sm text-green-700 mb-1">
                            <span className="font-semibold">Raw Kelly:</span>{" "}
                            {(bestBet.rawKelly * 100).toFixed(1)}% → Fractional: {(bestBet.fraction * 100).toFixed(2)}%
                          </p>
                          <p className="text-sm text-green-700 font-bold text-lg">
                            <span className="font-semibold">💵 Recommended Bet:</span>{" "}
                            ${bestBet.amount.toFixed(2)}
                          </p>
                        </div>
                      )}

                      {!bestBet && (redOdds || blueOdds) && (
                        <div className="mt-4 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                          <p className="text-sm text-gray-600">
                            No value bet detected - insufficient edge or odds fairly priced
                          </p>
                        </div>
                      )}
                      
                      {!redOdds && !blueOdds && (
                        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                          <p className="text-sm text-blue-700">
                            💡 Enter odds above to see betting recommendations
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Betting Summary Calculator */}
            {(() => {
              const minEdge = 0.05;
              let totalWagered = 0;
              let totalToWin = 0;
              let numBets = 0;
              const betDetails = [];

              groupFights(eventData.predictions).forEach((prediction, idx) => {
                const redOdds = customOdds[idx]?.red ? Number(customOdds[idx].red) : null;
                const blueOdds = customOdds[idx]?.blue ? Number(customOdds[idx].blue) : null;
                
                const redKelly = redOdds ? calculateKellyBet(prediction.red_win_prob, redOdds, bankroll, kellyFraction, maxFraction) : null;
                const blueKelly = blueOdds ? calculateKellyBet(prediction.blue_win_prob, blueOdds, bankroll, kellyFraction, maxFraction) : null;
                
                let bestBet = null;
                if (redKelly && redKelly.edge > minEdge && redKelly.fraction > 0) {
                  bestBet = { ...redKelly, fighter: prediction.red_fighter, odds: redOdds };
                }
                if (blueKelly && blueKelly.edge > minEdge && blueKelly.fraction > 0) {
                  if (!bestBet || blueKelly.edge > bestBet.edge) {
                    bestBet = { ...blueKelly, fighter: prediction.blue_fighter, odds: blueOdds };
                  }
                }

                if (bestBet) {
                  const potentialProfit = bestBet.odds > 0 
                    ? (bestBet.amount * bestBet.odds / 100)
                    : (bestBet.amount * 100 / Math.abs(bestBet.odds));
                  
                  totalWagered += bestBet.amount;
                  totalToWin += (bestBet.amount + potentialProfit);
                  numBets++;
                  betDetails.push({
                    fighter: bestBet.fighter,
                    bet: bestBet.amount,
                    toWin: bestBet.amount + potentialProfit
                  });
                }
              });

              const avgBet = numBets > 0 ? totalWagered / numBets : 0;
              const potentialProfit = totalToWin - totalWagered;
              const potentialROI = totalWagered > 0 ? (potentialProfit / totalWagered * 100) : 0;

              if (numBets === 0) return null;

              return (
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300 rounded-lg p-6 shadow-lg">
                  <h3 className="text-2xl font-bold text-green-900 mb-4 flex items-center">
                    💰 Betting Summary
                  </h3>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-white rounded-lg p-4 shadow">
                      <p className="text-xs text-gray-600 mb-1">Number of Bets</p>
                      <p className="text-2xl font-bold text-gray-900">{numBets}</p>
                    </div>
                    <div className="bg-white rounded-lg p-4 shadow">
                      <p className="text-xs text-gray-600 mb-1">Total Wagered</p>
                      <p className="text-2xl font-bold text-blue-600">${totalWagered.toFixed(2)}</p>
                    </div>
                    <div className="bg-white rounded-lg p-4 shadow">
                      <p className="text-xs text-gray-600 mb-1">Total To Win</p>
                      <p className="text-2xl font-bold text-green-600">${totalToWin.toFixed(2)}</p>
                    </div>
                    <div className="bg-white rounded-lg p-4 shadow">
                      <p className="text-xs text-gray-600 mb-1">Potential Profit</p>
                      <p className="text-2xl font-bold text-emerald-600">+${potentialProfit.toFixed(2)}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-white rounded-lg p-4 shadow">
                      <p className="text-sm text-gray-600 mb-2">Average Bet Size</p>
                      <p className="text-xl font-bold text-gray-900">${avgBet.toFixed(2)}</p>
                    </div>
                    <div className="bg-white rounded-lg p-4 shadow">
                      <p className="text-sm text-gray-600 mb-2">Potential ROI</p>
                      <p className="text-xl font-bold text-purple-600">{potentialROI.toFixed(2)}%</p>
                    </div>
                  </div>

                  <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                    <p className="text-xs text-blue-700">
                      <span className="font-semibold">Note:</span> This shows total if you bet on all {numBets} recommended fights. 
                      Potential profit assumes all bets win (actual results will vary).
                    </p>
                  </div>
                </div>
              );
            })()}

            {/* Skipped Fights */}
            {eventData.skipped_fights && eventData.skipped_fights.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                <h3 className="text-lg font-bold text-yellow-900 mb-3">
                  Fights Skipped (Insufficient Data)
                </h3>
                <ul className="list-disc list-inside space-y-1">
                  {eventData.skipped_fights.map((fight, idx) => (
                    <li key={idx} className="text-yellow-800">
                      {fight[0]} vs {fight[1]}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EventPredictor;
