# UFC Fight Predictor

The new and improved UFC AI model is consistently averaging around $100 profit over the past year of UFC events in 2023, when starting with $1000 (10% profit). With a robust accuracy of 64%, it can accurately identify winning percentages of each fighter which is used in the Kelly Criterion to determine how much to bet on each fight. The best result we have simulated was turning $1000 on February 22, 2022 to $3042.19 by December 16, 2023, as well as averaging $1600 on this time period, which shows what could possibly happen in the long term if the model learns the fighting meta well. Previous research studies have found accuracies maxing out at around 63-64%. The code and process can be viewed at https://github.com/jazyz/UFCFightPredictor.

# How To Use betUFC

## Predictor
To predict the outcome of a fight, enter the names of 2 different fighters into the UFC Fight Predictor. Behind the scenes, the model will be trained and the result will be shown on screen. The model does not take into account weight classes, so please enter 2 fighters in the same weight class for accuracy. The statistics of each fighter are up to date to what is currently available from ufcstats.com.

## Testing
To test the model on past UFC events, visit the testing page and enter the start year and end year. We will then simulate bets using the predicted results that the model gives us, making sure to only use data obtained before the time of each fight. The bankroll after each bet will be plotted at the top, and you can view the predictions below. Currently the model goes from $1000 to $1389 from 2021 to 2024, using a normal Kelly Criterion betting strategy.
