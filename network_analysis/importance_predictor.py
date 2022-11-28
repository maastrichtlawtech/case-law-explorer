import sys
from os.path import dirname, abspath
import math

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import precision_recall_curve
from sklearn.metrics import average_precision_score
from sklearn.metrics import PrecisionRecallDisplay
from sklearn.metrics import auc
import matplotlib.pyplot as plt
from sklearn.metrics import f1_score as f1
from imblearn.over_sampling import RandomOverSampler
from imblearn.under_sampling import RandomUnderSampler
from collections import Counter 

sys.path.append(dirname(dirname(abspath(__file__)))) # This allows imports from another folder.
from definitions.storage_handler import CSV_ECHR_CENTRALITIES, CSV_ECHR_YEARS, CSV_ECHR_CASES


def one_hot_encode_labels(labels): #do i need num_classes?
    num_classes = labels.nunique()
    labels_encoded = np.zeros((labels.shape[0], num_classes))
    for label_no in range(labels.shape[0]):
        labels_encoded[label_no, labels.iloc[label_no]-1] = 1
    return labels_encoded


def evaluate(y_val, prediction_probabilities, predictions, classes):
    """
    Evaluate a prediction model using the area under the precision recall curve. Multi-class 
    classification is done by micro averaging the confusion matrices.
    """
    # One hot encode the labels
    y_val_encoded = one_hot_encode_labels(y_val)
    # Micro-average the confusion matrices.
    precisions, recalls, _ = precision_recall_curve(y_val_encoded.ravel(), prediction_probabilities.ravel())
    # Sort the recall and reorder the precision based on the new order so the auc can be calculated.
    recalls, precisions = (list(t) for t in zip(*sorted(zip(recalls, precisions))))
    curve = [recalls, precisions]
    auc_score = auc(recalls, precisions)
    # Calculate the f1 score.
    f1_score = f1(y_val, predictions, labels=classes, average="micro")
    return curve, auc_score, f1_score
    

def cross_validate(data, num_folds=10, repetitions=3, class_weight=None, sampling=None, verbose=0):
    """
    Train the model leaving out a different fold each time and repeat this process a number of
    times. Score each trained model using the average area under the precision recall curve and 
    the average F1 score. These averages are taken across all folds and repetitions.
    """
    auc_scores = np.zeros(num_folds*repetitions)
    f1_scores = np.zeros(num_folds*repetitions)
    fold_size = math.floor(data.shape[0]/num_folds)
    curves = []
    for repetition in range(repetitions):
        data_shuffled = data.sample(frac=1)
        for k in range(num_folds):
            val_start_index = k*fold_size
            val_end_index = val_start_index+fold_size
            data_train = pd.concat([data_shuffled.iloc[:val_start_index], data_shuffled.iloc[val_end_index:]])
            data_val = data_shuffled.iloc[val_start_index:val_end_index]
            X_train = data_train.drop("importance", axis=1)
            y_train = data_train["importance"] 
            X_val = data_val.drop("importance", axis=1)
            y_val = data_val["importance"]
            if sampling == "over":
                class_counts = dict(Counter(y_train))
                maximum_class_count = max(class_counts.values())
                for key in class_counts.keys():
                    class_counts[key] = maximum_class_count
                oversample = RandomOverSampler(sampling_strategy=class_counts)
                X_train, y_train = oversample.fit_resample(X_train, y_train)
            elif sampling == "under":
                class_counts = dict(Counter(y_train))
                minimum_class_count = min(class_counts.values())
                for key in class_counts.keys():
                    class_counts[key] = minimum_class_count
                undersample = RandomUnderSampler(sampling_strategy=class_counts)
                X_train, y_train = undersample.fit_resample(X_train, y_train)
            model = LogisticRegression(multi_class="multinomial", solver="lbfgs", penalty="l2", C=0.8, class_weight=class_weight)
            model.fit(X_train, y_train)
            prediction_probabilities = model.predict_proba(X_val)
            predictions = model.predict(X_val)
            curve, auc_score, f1_score = evaluate(y_val, prediction_probabilities, predictions, np.unique(y_train))
            auc_scores[(repetition*num_folds)+k] = auc_score
            f1_scores[(repetition*num_folds)+k] = f1_score
            curves.append(curve)
    mean_auc_score = np.average(auc_scores)
    mean_f1_score = np.average(f1_scores)
    # Optionally plot the precision recall curves and show the auc and f1 score.
    if verbose == 1:
        for curve in curves:
            plt.plot(curve[0], curve[1])
        plt.show()
        print("a.u.c.   {}".format(mean_auc_score))
        print("f1 score {}\n".format(mean_f1_score))
    return model, mean_auc_score, mean_f1_score 

#centralities = pd.read_csv(CSV_ECHR_CENTRALITIES).fillna(0)
centralities = pd.read_csv(CSV_ECHR_CENTRALITIES).drop(["Unnamed: 0"], axis=1).fillna(0) # this can be removed after data is regenerated as this column will no longer be present
years = pd.read_csv(CSV_ECHR_YEARS)
data = pd.merge(centralities, years, on="ecli", how="inner").drop(["ecli"], axis=1)
print("baseline")
model, auc_score_average, f1_score_average = cross_validate(data, verbose=1)
X_test = data[data["importance"] == 2].drop("importance", axis=1)
y_test = data["importance"][data["importance"] == 2]
print(model.predict(X_test))
print(y_test.to_numpy())
print(Counter(model.predict(X_test)))

print("class weighting")
model, auc_score_average, f1_score_average = cross_validate(data, class_weight="balanced", verbose=1)
X_test = data[data["importance"] == 2].drop("importance", axis=1)
y_test = data["importance"][data["importance"] == 2]
print(model.predict(X_test))
print(y_test.to_numpy())
print(Counter(model.predict(X_test)))

print("under sampling")
model, auc_score_average, f1_score_average = cross_validate(data, sampling="under", verbose=1)
X_test = data[data["importance"] == 2].drop("importance", axis=1)
y_test = data["importance"][data["importance"] == 2]
print(model.predict(X_test))
print(y_test.to_numpy())
print(Counter(model.predict(X_test)))

print("over sampling")
model, auc_score_average, f1_score_average = cross_validate(data, sampling="over", verbose=1)
X_test = data[data["importance"] == 2].drop("importance", axis=1)
y_test = data["importance"][data["importance"] == 2]
print(model.predict(X_test))
print(y_test.to_numpy())
print(Counter(model.predict(X_test)))
