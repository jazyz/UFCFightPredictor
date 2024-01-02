# UFC Fight Predictor

# V4 Alpha Model

The new and improved UFC AI model is consistently averaging around $100 profit over the past year of UFC events in 2023, when starting with $1000 (10% profit). With a robust accuracy of 64%, it can accurately identify winning percentages of each fighter which is used in the Kelly Criterion to determine how much to bet on each fight. The best result we have simulated was turning $1000 on February 22, 2022 to $3042.19 by December 16, 2023, as well as averaging $1600 on this time period, which shows what could possibly happen in the long term if the model learns the fighting meta well. Previous research studies have found accuracies maxing out at around 63%.

## The Pipeline

## Data

### Web Scraping
All of the data was scraped from ufcstats.com. Previously, we had scraped data for each fighter as well as their fight histories and statistics, stored in an SQL database. However, in order to get more detailed fight statistics, we had to revamp the scraper entirely. We have now collected stats such as strike accuracy, control time, and submissions attempts for every fight from 1994 to 2023. The collected statistics are stored inside the data folder.

### Data Processing and Cleaning 
First, we need to clean the data, removing incomplete values, outdated fights, and duplicated data that was scraped. We also need to process all the data in a way which our machine learning model can understand, and retrieve all the raw numbers. This is done within modify_fights.py.

### Feature Engineering

With around 15 base stats for each fight, we now process the statistics in order to create expressive and predictive features. In order to predict a fight, we need the past fight histories of both fighters. The data scraped tells us which fighter is in the red corner and which fighter is in the blue corner. For simplicity in code, we call them Red and Blue.

By looping through all fights from past to present, we can dynamically compute stats from their past fights and then use those stats to predict a current fight. By doing this, we make sure that only data accessible before a fight has happened is used to predict a fight. Without doing this, our model accuracy would be up to 80+%, a mistake that some predictors with absurdly high accuracy may have.

Over 180+ features are engineering from these 15 base stats. For each base stat, such as significant strikes landed, we compute the number landed per minute, the accuracy of strikes, the difference between how many strikes you landed and how many strikes you took, the percentages of strikes you dodged, etc. Then, these stats are accumulated and processed into a weighted average which weighs recent fights much heavier than past, in order to get an accurate picture of each fighter's skills at different points in time. These in-depth statistics are then fed into the LightGBM ML model to be used to predict fights. This process is done within process_fights_alpha.py.

## Model

### LightGBM
We chose LightGBM (Light Gradient Boosting Machine), a tree-based learning algorithm, due to its exceptional speed, efficiency, and predicting power. LightGBM excels in capturing complex, non-linear relationships within UFC fight data, providing valuable insights into feature importance and tuning. With the new Alpha model, our accuracies were much more consistent than before. With much less features in our previous model, changing a few features could lead to dramatic changes in accuracy. Now that we have more robust data with a much wider selection of features, the reliability of the model was greatly increased. The code can be found within ml_alpha.py.

### Feature Selection

With so many features, it's important to select those which actually help the model. We prune out features which have high correlation with each other, as well as features which have low impact on the model. This reduces noise and helps the model pick out the correct percentages.

### Hyperparameter Tuning and Trials
LightGBM allows you to fine-tune your model, setting parameters such as learning rate, number of leaves in a tree, etc. These can all have great impacts on the predictions that the model makes. We utilized the optuna library to run trails in order to select the best hyperparameters for the model. Our current model accuracy is 64%. 

## Testing

To test our predictions on past fight cards from ufc.com, we use the testing folder. First, go to ml_alpha_testing.py. Edit the train/test split so that the test set contains all fight card fights which we want to evaluate. The train set should be disjoint from this test set. Then, edit testing_alpha_clean.py to set the range of event URLs to be tested. To perform tests, first run ml_alpha_testing.py, then testing_alpha_clean.py. The results will be written to test_results/testing_alpha_clean.txt, and the bankroll will be automatically graphed. By default, we set the test set to 10% of the fights in our database, which is around the past year of data.

## Results

Testing on the fight cards in 2023, we ran 10 separate trials with different tuned hyperparameters, and averaged an $1100 final bankroll starting from $1000. We used a conservative 0.05 Kelly Criterion betting strategy, which helps us determine what fraction of our bankroll to wager on each bet. Testing on the fight cards from both 2022 and 2023 with a more risky 0.1 Kelly Criterion, we average a final bankroll of $1600, while maxing out at around $3000. We found that our model is consistently gaining money and can sometimes go up to $2000 or $3000 over a longer period of time, while only going down to around $750. Starting with $1000, for 73/86 or 85% of the trials, the model goes above $1000, going down only 13/86 or 15% of the trials. 

## How to Bet on the Next Fight Card

To bet on the next fight card, we use predict_fights_alpha.py. After pasting the ufcstats.com url into events_url, you can run the file which scrapes all the names of the fighters on the card. Given we have enough data on both fighters (i.e. both fighters are not debuting) their stats will be processed together and put into predict_fights_alpha.csv in the data folder. Next we run ml_alpha.py which trains the model and reads from the csv to make predictions. These results take into account all the selected stats and output winning and losing probabilities for each fighter. These proabbilities are outputted to predicted_fights_alpha_results_clean.csv. Finally, we use betting_alpha.py which reads the fighters and the odds of each fight from ufc.com to make bets. After getting the probabilities from predicted_fights_alpha_results_clean.csv, based on the odds and kelly criterion we can automate which fights we will bet on. It should also be noted that we take the probability closer to the odds in order to reduce error in predicting.

## Other Studies

Stanford University: 62.6%
https://cs229.stanford.edu/proj2019aut/data/assignment_308875_raw/26426025.pdf

MMA AI: 64%
https://www.mma-ai.net/

Tilburg University: 62% (RandomForest, Neural Network)
http://arno.uvt.nl/show.cgi?fid=156304

# V1-V3.1 Model (Old):

The old code can be found within the oldModel folder.
UFCFightPredictor is a Python-based tool that leverages web scraping techniques to gather data from ufcstats.com and employs machine learning techniques like LightGBM (Light Gradient Boosting Machine) model for fight predictions. With a dataset comprising over 19,000 fights and data points, UFCFightPredictor has achieved a remarkable 64% accuracy, surpassing previous research paper accuracies of 62%. Simulating for the last 2 months, we have managed to increase our money to 110% of the starting bankroll.

## Testing One Event

1. Run process_fights_elo.py to process and update fighter's stats from elofightstats.csv, which is then exported to fighter_stats.csv
2. Then run predict_fights_elo.py with the link (from ufcstats.com) of the event to parse all the names of the fighters on the card and their stats from fighter_stats.csv. The fights and their copy (AvB and BvA) will be exported to predict_fights_elo.csv
3. Run ml_training_duplication.py with the correct training date. The model's predictions will be exported to ml_elo.txt
4. Run betting.py to parse the names of the fighters from ml_elo.txt and get the corresponding id to that fight. Betting.py will webscrape the names of the fighters from ufc.com/events with the betting odds and cross-check with ml_elo.txt. Then it will find the win and loss percentage for each fighter respectivley and print these results to predictions.txt.

## Testing Multiple Events

1. In testing.py, set the number of pages you want from ufc.com/events/page=? to go back to a certain date
2. In predict_fights_elo.py, set the event_url to break the event link your testing until from ufcstats.com
3. Run testing.py and wait for results in testing.txt (testing optmization coming soon)

## Web Scraping

Using **Python BeautifulSoup** library we webscraped past history of all UFC and UFC related (TUF, DWCS, Pride, etc.) since 1993. From [ufcstats.com](ufcstats.com) going from each fighter's last name we look at their past fight history and gather data from their fights like number of strikes they landed vs number of strikes their opponent landed. Storing these values in an **SQL database** we're able to use these values later for data processing.

## Data Processing and Cleaning

### Feature Engineering

### Hyperparameter Tuning

### Trials

## Training the Model

UFCFightPredictor relies on LightGBM (Light Gradient Boosting Machine) due to its exceptional speed, efficiency in handling large datasets, and its ability to deliver high prediction accuracy, surpassing the community standard at 64%. LightGBM excels in capturing complex, non-linear relationships within UFC fight data, providing valuable insights into feature importance, and offering customization options for fine-tuning.

## Challenges

### Backtesting & Data Leakage

### Automation

### Feature Testing

## Versions

v1:
75% Accuracy on UFC 292 (9/12 fights predicted correctly) using power rating algorithm

v2:
Achieved 67% accuracy on test set with data leakage using a machine learning RandomForest model

v2.1:
Achieved 68% accuracy on test set with data leakage using Light Gradient Boosting Machine model

v3.0:
Achieved 64% accuracy on test set without data leakage using Light Gradient Boosting Machine model

v3.1:
Tuned LightGBM model and achieved 67% accuracy on the last 3 months of fights
