import re
import os
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('agg')

# Read the text file
with open('predictions.txt', 'r') as file:
    data = file.read()

# Extract bankroll numbers using regex
bankroll_pattern = r'\*\*\* Bankroll: \$([\d.]+) \*\*\*'
bankrolls = re.findall(bankroll_pattern, data)

# Convert bankroll strings to float
bankrolls = list(map(float, bankrolls))

# Plot the graph
plt.figure(figsize=(10, 6))
plt.plot(range(1, len(bankrolls) + 1), bankrolls, marker='o')
plt.xlabel('Weeks')
plt.ylabel('Bankroll ($)')
plt.title('Bankroll Over Fight Cards')
plt.grid(True)
# plt.show()
plt.savefig(os.path.join("data", "predictions_bankroll_plot.png"))  # Save the plot as an image file
plt.close()  # Close the plot