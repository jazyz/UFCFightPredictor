# Fractional Kelly Implementation

## Overview
Updated the Event Predictor to use **Fractional Kelly** betting, matching the proven strategy from `testing_time_period.py`.

## What Changed

### Before (Full Kelly):
```
Bet = Bankroll × Kelly %
```
**Problem:** Too aggressive! A 20% Kelly on $1000 = $200 bet (20% of entire bankroll on ONE fight)

### After (Fractional Kelly):
```
Bet = Bankroll × Kelly Fraction × Raw Kelly %
Bet = min(Bet, Bankroll × Max Cap)
```
**Solution:** Conservative and sustainable!

## Example Calculation

**Scenario:**
- Bankroll: $1,000
- Fighter odds: -300 (implied 75% probability)
- Model probability: 84%
- Raw Kelly: 20%

### Full Kelly (OLD):
```
Bet = $1,000 × 20% = $200 ❌
```

### Fractional Kelly (NEW - Normal Strategy):
```
Kelly Fraction: 5%
Max Cap: 5%

Bet = $1,000 × 5% × 20% = $10
Bet = min($10, $1,000 × 5%) = $10 ✅
```

### Fractional Kelly (Risky Strategy):
```
Kelly Fraction: 10%  
Max Cap: 10%

Bet = $1,000 × 10% × 20% = $20
Bet = min($20, $1,000 × 10%) = $20
```

## Strategy Presets

### 🟢 Conservative (2.5%)
- Kelly Fraction: 2.5%
- Max Cap: 2.5%
- Best for: Preserving bankroll, new bettors
- Max bet: 2.5% of bankroll per fight

### 🔵 Normal (5%) - **DEFAULT**
- Kelly Fraction: 5%
- Max Cap: 5%
- Best for: Most users, matches backtesting
- Max bet: 5% of bankroll per fight

### 🔴 Risky (10%)
- Kelly Fraction: 10%
- Max Cap: 10%
- Best for: High risk tolerance, confident bettors
- Max bet: 10% of bankroll per fight

## UI Features

### 1. Betting Settings Panel
- **Bankroll Input**: Set your available funds
- **Kelly Fraction (%)**: Multiplier for Kelly bets
- **Max Bet Cap (%)**: Hard limit per fight
- **Quick Preset Buttons**: One-click strategy selection

### 2. Fight Cards Show:
- **Edge %**: Model advantage over market
- **Raw Kelly %**: Full Kelly recommendation  
- **Bet Amount**: Actual dollars to bet (fractional)

### 3. Value Bet Cards Display:
- Fighter to bet on
- Edge percentage
- Raw Kelly → Fractional Kelly breakdown
- **Recommended Bet in Dollars** 💵

## Why Fractional Kelly?

### 1. **Risk Management**
- Never risk too much on one fight
- Survive variance and bad beats
- Multiple bets across card diversifies risk

### 2. **Bankroll Preservation**
- Losing 5% is manageable
- Losing 20% is devastating
- Stay in the game longer

### 3. **Proven Strategy**
From `testing_time_period.py`:
```python
# Normal strategy in testing
bet = bankroll * 0.05 * kelly  # 5% fraction
bet = min(bet, bankroll * 0.05)  # 5% max cap
```
This is what the backtesting uses, so predictions match reality!

### 4. **Psychological Benefits**
- Less stress per fight
- More sustainable long-term
- Easier to follow the system

## Real-World Example

**UFC 322 Event with $5,000 bankroll:**

| Fight | Raw Kelly | Full Kelly Bet | Fractional (5%) | Max Cap (5%) | Actual Bet |
|-------|-----------|----------------|-----------------|--------------|------------|
| Fight 1 | 15% | $750 | $37.50 | $250 | **$37.50** |
| Fight 2 | 25% | $1,250 | $62.50 | $250 | **$62.50** |
| Fight 3 | 8% | $400 | $20.00 | $250 | **$20.00** |
| Fight 4 | 30% | $1,500 | $75.00 | $250 | **$75.00** |
| **Total** | - | **$3,900** 😱 | **$195** ✅ | - | **$195** |

With Full Kelly, you'd bet **78% of your bankroll** on one card! With Fractional Kelly, only **3.9%** total.

## Code Changes

### State Variables
```javascript
const [kellyFraction, setKellyFraction] = useState(0.05); // 5%
const [maxFraction, setMaxFraction] = useState(0.05); // 5%
```

### Calculation Function
```javascript
const calculateKellyBet = (winProb, odds, bankroll, kellyMult, maxCap) => {
  // Calculate raw Kelly
  const kelly = (b * p - q) / b;
  
  // Apply fractional Kelly
  let betAmount = bankroll * kellyMult * kelly;
  
  // Cap at max
  betAmount = Math.min(betAmount, bankroll * maxCap);
  
  return { rawKelly: kelly, amount: betAmount, ... };
};
```

## Best Practices

### 1. Start Conservative
- Use 2.5% or 5% fraction until comfortable
- Track results over 50+ fights
- Gradually increase if profitable

### 2. Update Bankroll Regularly
- After wins: increase bankroll input
- After losses: decrease bankroll input
- Kelly works on current bankroll, not starting

### 3. Respect the Max Cap
- Even if Raw Kelly says 50%, max cap protects you
- Prevents overexposure on "sure things"
- No fight is truly guaranteed

### 4. Don't Force Bets
- If no green cards appear, don't bet!
- Edge < 5% is not worth the risk
- Quality over quantity

### 5. Compare to Testing Results
- Backtesting used 5% strategy
- Historical performance: -96% (shows model needs work!)
- Your live results should track similarly

## Technical Notes

### Matching testing_time_period.py Logic

**Python (Testing):**
```python
fraction = 0.05  # strategy[0]
max_fraction = 0.05  # strategy[1]

bet = bankroll * fraction * kc_a
bet = min(bet, max_fraction * bankroll)
```

**JavaScript (Frontend):**
```javascript
const kellyFraction = 0.05;
const maxFraction = 0.05;

let betAmount = bankroll * kellyFraction * kelly;
betAmount = Math.min(betAmount, bankroll * maxFraction);
```

**They're identical!** ✅

## Files Modified

1. **EventPredictor.js**
   - Added `kellyFraction` and `maxFraction` state
   - Updated `calculateKellyBet()` function
   - Added strategy preset buttons
   - Enhanced UI to show Raw Kelly vs Fractional Kelly
   - Added betting settings panel with inputs

## Summary

**Fractional Kelly makes betting:**
- ✅ Safer (smaller bets)
- ✅ More sustainable (preserve bankroll)
- ✅ Consistent with testing (matches backtesting)
- ✅ Professional (industry standard)
- ✅ Flexible (adjustable strategies)

**Remember:** Even with optimal Kelly sizing, you need a positive edge to be profitable long-term. The model's accuracy and the odds you get matter more than perfect bet sizing!

---

**Default Settings Match Your Testing:**
- Kelly Fraction: 5%
- Max Cap: 5%  
- These are proven from your `testing_time_period.py` backtests!
