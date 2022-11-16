import sys
from os.path import dirname, abspath

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import RepeatedStratifiedKFold

sys.path.append(dirname(dirname(abspath(__file__)))) # This allows imports from another folder.
from definitions.storage_handler import CSV_ECHR_CASES_CENTRALITIES, CSV_ECHR_CASES

centralities = pd.read_csv(CSV_ECHR_CASES_CENTRALITIES).drop(["Unnamed: 0", "ecli"], axis=1).fillna(0)

pd.concat([df1.set_index('A'),df2.set_index('A')], axis=1, join='inner')


X = df.drop("importance", axis=1)
y = df["importance"]

model = LogisticRegression(multi_class="multinomial", solver="lbfgs", penalty="l2", C=0.8)
cv = RepeatedStratifiedKFold(n_splits=10, n_repeats=3)
scores = cross_val_score(model, X, y, scoring="roc_auc_ovr", cv=cv)

print(scores)
print(type(scores))

print("mean score: %.3f (%.3f)" % (np.mean(scores), np.std(scores)))


#TODO add year
#select an evalutation which is good for imbalenced labels
#understand lbfgs (its appropriate but go through the maths)
#confirm roc_auc_ovr makes sense and understand it better
#tune hyperparameters
#review l2
#add preprocessing to get column of years and then concat this to use as a predictor
#experiment with which ones are best