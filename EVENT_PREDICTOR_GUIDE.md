# UFC Event Predictor Feature

## Overview
The Event Predictor allows you to input a UFC event URL from ufcstats.com and automatically generate predictions for all fights on the card, along with betting recommendations based on the Kelly Criterion.

## Features

### 1. **Automatic Fight Extraction**
- Scrapes all fights from a UFC event page
- Handles fighter name variations automatically

### 2. **ML Predictions**
- Uses the retrained single model (`lgbm_single_model.joblib`)
- Generates win probabilities for both fighters
- Processes both Red vs Blue and Blue vs Red permutations for accuracy

### 3. **Betting Recommendations**
- Calculates edge (model probability - market implied probability)
- Only recommends bets with >5% edge
- Uses Kelly Criterion for optimal bet sizing
- Shows percentage of bankroll to wager

### 4. **Beautiful UI**
- Modern, responsive design with Tailwind CSS
- Color-coded probability bars
- Green highlight for value bets
- Shows skipped fights (insufficient data)

## How to Use

### Backend
1. **Start Flask server:**
   ```bash
   python app.py
   ```

2. **Test standalone script:**
   ```bash
   python predict_event.py
   ```

### Frontend
1. **Start React dev server:**
   ```bash
   cd frontend
   npm start
   ```

2. **Navigate to Event Predictor:**
   - Click "Predict Event" in the navbar
   - Or go to `http://localhost:3000/event`

3. **Enter Event URL:**
   - Go to [UFCStats.com](http://ufcstats.com)
   - Find your event (e.g., UFC 322)
   - Copy the event details URL (format: `http://ufcstats.com/event-details/[EVENT_ID]`)
   - Paste into the input field
   - Click "Predict Event"

## Example URLs

- **UFC 322:** `http://ufcstats.com/event-details/38e5d9dcb0fddc42`
- **Any upcoming event from:** [http://ufcstats.com/statistics/events/upcoming](http://ufcstats.com/statistics/events/upcoming)
- **Past events from:** [http://ufcstats.com/statistics/events/completed](http://ufcstats.com/statistics/events/completed)

## Technical Details

### Backend (`predict_event.py`)
```python
predict_event(event_url) -> {
    "event_name": str,
    "event_url": str,
    "predictions": [
        {
            "red_fighter": str,
            "blue_fighter": str,
            "red_win_prob": float,
            "blue_win_prob": float,
            "predicted_winner": str
        }
    ],
    "odds": {
        "Fighter1 vs Fighter2": {
            "red_odds": float,
            "blue_odds": float
        }
    },
    "skipped_fights": [[str, str]]
}
```

### Flask Endpoint
- **Route:** `/predict_event`
- **Method:** POST
- **Body:** `{"event_url": "http://..."}`
- **Response:** JSON with predictions and odds

### React Component (`EventPredictor.js`)
- **Route:** `/event`
- **Features:**
  - URL input validation
  - Loading states
  - Error handling
  - Probability visualization
  - Betting recommendation cards
  - Kelly Criterion calculation

## Kelly Criterion Formula

```
f = (bp - q) / b

Where:
- b = decimal odds - 1
- p = win probability (model)
- q = 1 - p (lose probability)
- f = fraction of bankroll to bet
```

## Value Bet Detection

A bet is recommended when:
```
Model Probability - Implied Probability > 5%
```

Example:
- Model says 60% win probability
- Odds imply 50% win probability
- Edge = 10% → BET!

## Files Modified/Created

### New Files
1. `predict_event.py` - Backend script for event prediction
2. `frontend/src/components/EventPredictor.js` - React component
3. `EVENT_PREDICTOR_GUIDE.md` - This documentation

### Modified Files
1. `app.py` - Added `/predict_event` endpoint
2. `frontend/src/App.js` - Added route for EventPredictor
3. `frontend/src/components/Navbar.js` - Added navigation link

## Future Enhancements

1. **Odds Integration**
   - Real-time odds scraping from betting sites
   - Multiple bookmaker comparison
   - Line movement tracking

2. **Historical Performance**
   - Show model accuracy for past events
   - Track betting ROI by event
   - Fighter-specific model performance

3. **Advanced Filters**
   - Filter by weight class
   - Show only value bets
   - Sort by edge/Kelly size

4. **Export Features**
   - Export predictions to CSV
   - Generate betting slip
   - Share predictions via link

## Troubleshooting

### "No fights found"
- Verify the URL is from ufcstats.com/event-details/
- Check if the event page has fight data loaded

### "Fighter not found in CSV"
- Fighter may be too new (not in training data)
- Fighter may have <2 total fights
- Check name spelling matches exactly

### Model not loading
- Ensure `auto_retrain.py` has been run
- Verify files exist:
  - `saved_models/lgbm_single_model.joblib`
  - `saved_preprocessing/label_encoder_single.joblib`
  - `saved_preprocessing/selected_columns_single.json`

## Requirements

### Backend
```
flask
flask-cors
requests
beautifulsoup4
pandas
numpy
joblib
scikit-learn
lightgbm
```

### Frontend
```
react
react-router-dom
axios
react-toastify
tailwindcss
```

## Contributing

When adding new features:
1. Update this documentation
2. Test with multiple event URLs
3. Verify odds integration works when available
4. Ensure mobile responsiveness

---

**Built with ❤️ for UFC Fight Predictor**
