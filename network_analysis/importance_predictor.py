import sys
from os.path import dirname, abspath

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import RepeatedStratifiedKFold

sys.path.append(dirname(dirname(abspath(__file__)))) # This allows imports from another folder.
from definitions.storage_handler import CSV_ECHR_CASES_CENTRALITIES, CSV_ECHR_YEARS, CSV_ECHR_CASES

centralities = pd.read_csv(CSV_ECHR_CASES_CENTRALITIES).fillna(0)
years = pd.read_csv(CSV_ECHR_YEARS)
data = pd.merge(centralities, years, on="ecli", how="inner").drop(["ecli"], axis=1)
data = data.drop(["year"], axis = 1)

num_test = 50
num_train = data.shape[0]-num_test
X_train = data.drop("importance", axis=1).iloc[:num_train]
y_train = data["importance"].iloc[:num_train]
X_test = data.drop("importance", axis=1).iloc[num_train:]
y_test = data["importance"].iloc[num_train:]

model = LogisticRegression(multi_class="multinomial", solver="lbfgs", penalty="l2", C=0.8)
cv = RepeatedStratifiedKFold(n_splits=10, n_repeats=3)
scores = cross_val_score(model.fit(X_train, y_train), X_train, y_train, scoring="roc_auc_ovr", cv=cv)
print(scores)
print("mean score: %.3f (%.3f)" % (np.mean(scores), np.std(scores)))
#model.fit(X_train, y_train)

predictions = model.predict(X_test)
print("predictions: ", predictions)
print("labels:      ", y_test.to_numpy())





#TODO add year
#select an evalutation which is good for imbalenced labels
#understand lbfgs (its appropriate but go through the maths)
#confirm roc_auc_ovr makes sense and understand it better
#tune hyperparameters
#review l2
#add preprocessing to get column of years and then concat this to use as a predictor
#experiment with which ones are best