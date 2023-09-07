odds = int(input())
prob_win = int(input())/100

if (odds < 0):
    n = 100 / -odds
    kc = (n * prob_win - (1 - prob_win)) / n
    print(kc)
else:
    n = odds / 100
    kc = (n * prob_win - (1 - prob_win)) / n
    print(kc)
