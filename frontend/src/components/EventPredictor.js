import React, { useState } from "react";
import axios from "axios";
import { baseURL } from "../constants";
import { toast } from "react-toastify";

const EventPredictor = () => {
  const [eventUrl, setEventUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [eventData, setEventData] = useState(null);
  const [error, setError] = useState(null);

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
      toast.success("Predictions generated successfully!");
    } catch (err) {
      const errorMsg = err.response?.data?.error || "Failed to generate predictions";
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const calculateKellyBet = (winProb, odds) => {
    if (!odds || odds === 0) return null;
    
    // Convert American odds to decimal
    const decimalOdds = odds > 0 ? (odds / 100) + 1 : (100 / Math.abs(odds)) + 1;
    
    // Kelly Criterion: f = (bp - q) / b
    // where b = decimal odds - 1, p = win probability, q = 1 - p
    const b = decimalOdds - 1;
    const p = winProb;
    const q = 1 - p;
    const kelly = (b * p - q) / b;
    
    return Math.max(0, kelly); // Never bet negative amounts
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
              <p className="text-gray-600">
                {groupFights(eventData.predictions).length} fights predicted
              </p>
            </div>

            {/* Predictions Grid */}
            <div className="grid gap-6 md:grid-cols-2">
              {groupFights(eventData.predictions).map((prediction, idx) => {
                const matchupKey = `${prediction.red_fighter} vs ${prediction.blue_fighter}`;
                const odds = eventData.odds?.[matchupKey];
                const bettingRec = getBettingRecommendation(prediction, odds);

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
                          <span className="text-sm text-gray-600">
                            {odds?.red_odds && formatOdds(odds.red_odds)}
                          </span>
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
                      </div>

                      {/* Blue Fighter */}
                      <div className="mb-4">
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-semibold text-gray-900">
                            {prediction.blue_fighter}
                          </span>
                          <span className="text-sm text-gray-600">
                            {odds?.blue_odds && formatOdds(odds.blue_odds)}
                          </span>
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
                      </div>

                      {/* Betting Recommendation */}
                      {bettingRec && (
                        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                          <p className="text-green-800 font-bold mb-2">
                            💰 Value Bet Detected
                          </p>
                          <p className="text-sm text-green-700 mb-1">
                            <span className="font-semibold">Bet on:</span> {bettingRec.fighter}
                          </p>
                          <p className="text-sm text-green-700 mb-1">
                            <span className="font-semibold">Edge:</span> {(bettingRec.edge * 100).toFixed(1)}%
                          </p>
                          <p className="text-sm text-green-700 mb-1">
                            <span className="font-semibold">Model Probability:</span>{" "}
                            {(bettingRec.probability * 100).toFixed(1)}%
                          </p>
                          <p className="text-sm text-green-700">
                            <span className="font-semibold">Kelly Criterion:</span>{" "}
                            {(bettingRec.kelly * 100).toFixed(1)}% of bankroll
                          </p>
                        </div>
                      )}

                      {!bettingRec && odds && (
                        <div className="mt-4 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                          <p className="text-sm text-gray-600">
                            No value bet - odds fairly priced
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

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
