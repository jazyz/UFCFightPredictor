bankroll = 1099.64

while True:
    odds = int(input())
    prob_win = float(input())
    kc = 0
    if (odds < 0):
        n = 100 / -odds
        kc = (n * prob_win - (1 - prob_win)) / n
    else:
        n = odds / 100  
        kc = (n * prob_win - (1 - prob_win)) / n
    if (kc > 0):
        bet = bankroll * (0.1) * kc
        potential_return = 0
        if (odds < 0):
            potential_return = bet * (100 / -odds)
        else:
            potential_return = bet * (odds / 100)
        print(f"${bet:.2f} (bet) pt: ${bet + potential_return:.2f} +${potential_return:.2f}")
    print(f"{kc:.2f}")