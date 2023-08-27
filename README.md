# UFC Fight Predictor

75% Accuracy on UFC 292 (9/12 fights predicted correctly) using power rating algorithm

Achieved 67% accuracy on test set using a machine learning RandomForest model

## Possible problems

data training:

- all fights are added after your first fight, which may show a potential problem
  - stats are very volatile in the first few fights
  - solution could be to "average opponent experience" to take into account how good the opponents were
