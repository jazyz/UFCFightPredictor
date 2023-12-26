# UFC Fight Predictor

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

### Getting "Good" Data

- Generating fake data to add to the training

## Versions

v1:
75% Accuracy on UFC 292 (9/12 fights predicted correctly) using power rating algorithm

v2:
Achieved 67% accuracy on test set with data leakage using a machine learning RandomForest model

v3:
Achieved 68% accuracy on test set with data leakage using Light Gradient Boosting Machine model

v4:
Achieved 64% accuracy on test set without data leakage using Light Gradient Boosting Machine model

v5:
Tuned LightGBM model and achieved 67% accuracy on the last 3 months of fights

Website at https://github.com/KoreaFriedChips/ufc

## Other Studies

Stanford University: 62.6%
https://cs229.stanford.edu/proj2019aut/data/assignment_308875_raw/26426025.pdf

MMA AI: 63.4%
https://www.mma-ai.net/

Tilburg University: 62% (RandomForest, Neural Network)
http://arno.uvt.nl/show.cgi?fid=156304
