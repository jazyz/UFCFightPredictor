# Custom Odds & Kelly Criterion Calculator

## Overview
Enhanced the Event Predictor page to allow users to input their own odds and bankroll, then automatically calculate Kelly Criterion bet sizing recommendations.

## New Features

### 1. **Bankroll Input**
- Located at the top of the event predictions
- Default: $1,000
- Adjustable to any amount
- Used for calculating bet amounts in dollars

### 2. **Custom Odds Inputs**
- Each fight has **two input fields** (one for each fighter)
- Accepts American odds format:
  - Negative odds (favorites): `-150`, `-200`, etc.
  - Positive odds (underdogs): `+130`, `+250`, etc.
- Pre-populated with scraped odds if available
- Updates calculations **in real-time** as you type

### 3. **Dynamic Kelly Calculations**
For each fighter with odds entered:
- **Edge %** - How much your model's probability exceeds the market's implied probability
- **Kelly Bet** - Exact dollar amount to bet based on Kelly Criterion
- Displayed below each fighter's probability bar

### 4. **Value Bet Detection**
Green card appears when:
- Edge > 5% (configurable in code)
- Kelly Criterion > 0
- Shows:
  - Which fighter to bet on
  - Edge percentage
  - Kelly percentage of bankroll
  - **Exact bet amount in dollars**

### 5. **Smart Notifications**
- 🟢 Green card: Value bet detected - bet this amount!
- ⚪ Gray card: No value - odds are fairly priced
- 🔵 Blue card: Enter odds to see recommendations

## How to Use

### Step 1: Load an Event
1. Go to Event Predictor page
2. Enter UFC event URL from ufcstats.com
3. Click "Predict Event"

### Step 2: Set Your Bankroll
1. Adjust the bankroll input at the top
2. Default is $1,000
3. Calculations update immediately

### Step 3: Enter Odds
1. Type odds for each fighter in the input fields
2. Use American odds format (e.g., `-150`, `+200`)
3. Odds will pre-populate if available from scraping

### Step 4: Review Recommendations
- Check the green cards for value bets
- See exact dollar amounts to bet
- Review edge % to assess confidence
- Compare predictions across all fights

## Example Workflow

```
Event: UFC 322
Bankroll: $5,000

Fight: Brendan Allen vs Reinier de Ridder
- Model says Allen has 58.6% chance to win
- You see Allen at -150 (implied 60% probability)
- Model probability (58.6%) < Market probability (60%)
- Result: No value bet

Fight: Drew Dober vs Kyle Prepolec  
- Model says Dober has 84.1% chance to win
- You see Dober at -300 (implied 75% probability)
- Model probability (84.1%) > Market probability (75%)
- Edge: 9.1%
- Kelly: 12.3% of bankroll
- Recommended Bet: $615.00 on Drew Dober ✅
```

## Kelly Criterion Formula

```javascript
Kelly % = (bp - q) / b

Where:
- b = decimal odds - 1
- p = win probability (from model)
- q = 1 - p (lose probability)

Bet Amount = Kelly % × Bankroll
```

## Safety Features

1. **Minimum Edge**: Only recommends bets with >5% edge
2. **Positive Kelly Only**: Never shows negative bet amounts
3. **Best Bet Selection**: If both fighters have value, shows the one with higher edge
4. **Real-time Validation**: Calculations update as you type

## Tips for Best Results

### 1. **Use Half Kelly**
Consider betting **half** the recommended Kelly amount for more conservative bankroll management:
```
Conservative Bet = Recommended Bet ÷ 2
```

### 2. **Shop for Lines**
- Check multiple sportsbooks
- Enter the **best odds** you can find
- Small differences in odds = big differences in Kelly

### 3. **Update Bankroll Regularly**
- Adjust after wins/losses
- Kelly works best with accurate bankroll tracking
- Consider setting a separate "betting bankroll"

### 4. **Don't Force Bets**
- No green card = no bet
- Trust the model's edge detection
- Patience is profitable

### 5. **Consider Variance**
- MMA is highly variant (knockouts, submissions)
- 5% edge minimum helps filter marginal bets
- Track results over 50+ fights, not individual events

## Technical Details

### State Management
```javascript
const [bankroll, setBankroll] = useState(1000);
const [customOdds, setCustomOdds] = useState({});
// customOdds format: { fightIndex: { red: -150, blue: +130 } }
```

### Kelly Calculation
```javascript
const calculateKellyBet = (winProb, odds, bankrollAmount) => {
  const decimalOdds = odds > 0 ? (odds / 100) + 1 : (100 / Math.abs(odds)) + 1;
  const b = decimalOdds - 1;
  const kelly = (b * winProb - (1 - winProb)) / b;
  const kellyFraction = Math.max(0, kelly);
  const betAmount = kellyFraction * bankrollAmount;
  
  return { fraction: kellyFraction, amount: betAmount, edge: ... };
};
```

### Edge Calculation
```javascript
Implied Probability = odds > 0 
  ? 100 / (odds + 100) 
  : Math.abs(odds) / (Math.abs(odds) + 100)

Edge = Model Probability - Implied Probability
```

## Files Modified

1. **EventPredictor.js**
   - Added `bankroll` state
   - Added `customOdds` state  
   - Added `handleOddsChange` function
   - Enhanced `calculateKellyBet` to return dollar amounts
   - Updated UI with input fields
   - Added real-time Kelly displays

## Future Enhancements

1. **Kelly Multiplier**: Add slider for full/half/quarter Kelly
2. **Bet History**: Track and export recommended bets
3. **ROI Calculator**: Show expected value across all bets
4. **Odds Import**: Paste multiple lines at once
5. **Comparison Mode**: Compare odds from different books
6. **Alert System**: Notify when high-edge bets appear

---

**Remember**: This tool provides recommendations based on mathematical edge. Always gamble responsibly and never bet more than you can afford to lose.
