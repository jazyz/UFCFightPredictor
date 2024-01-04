import matplotlib.pyplot as plt

def parse_bankrolls(file_contents):
    # Extracting bankroll values from the given text
    lines = file_contents.strip().split('\n')
    bankrolls = []
    for line in lines:
        if line.startswith('Bankroll:'):
            bankroll = float(line.split('$')[1])
            bankrolls.append(bankroll)
    return bankrolls

def prune_bankrolls(bankrolls):
    # Pruning the bankroll to only include values after the last value greater than $3000
    for i in range(len(bankrolls) - 1, -1, -1):
        if bankrolls[i] > 3000:
            return bankrolls[i + 1:]
    return bankrolls  # return all if no value is greater than $3000

def graph_bankrolls(bankrolls):
    # Graphing the bankrolls
    plt.figure(figsize=(10, 6))
    plt.plot(bankrolls, marker='o')
    plt.title('Bankroll Values in each Trial')
    plt.xlabel('Trial Number')
    plt.ylabel('Bankroll Value')
    plt.grid(True)
    plt.show()

def calculate_average_bankroll(bankrolls):
    # Calculating the average bankroll
    if bankrolls:
        average_bankroll = sum(bankrolls) / len(bankrolls)
    else:
        average_bankroll = 0
    return average_bankroll

def count_bankrolls(bankrolls):
    # Counting how many bankrolls are above and below $1000
    above_1000 = sum(1 for b in bankrolls if b > 1000)
    below_1000 = sum(1 for b in bankrolls if b < 1000)
    return above_1000, below_1000

# Example usage:
with open('test_results/results.txt', 'r') as file:
    file_contents = file.read()
    bankrolls = parse_bankrolls(file_contents)
    bankrolls = prune_bankrolls(bankrolls)
    average_bankroll = calculate_average_bankroll(bankrolls)
    above_1000, below_1000 = count_bankrolls(bankrolls)
    print("Average Bankroll: $", average_bankroll)
    print(f"{above_1000} bankrolls are above $1000 and {below_1000} are below $1000")
    graph_bankrolls(bankrolls)
