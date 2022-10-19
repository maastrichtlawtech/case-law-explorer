import numpy as np
import pandas as pd
from math import sqrt

import matplotlib.pyplot as plt

"""
Four Kendal rank coefficients, a, b, c, and a custom one d, are calculated in the same function
so that the concordant and discordant counts can be used for multiple metrics without needing to
repeat the loop. Separating these would reduce efficiancy significantly and and there is no
noticable slowdown when computing all four even when only one is necissary.
"""
def calculate_kendal_taus(metric):
    coefficients = {}
    sorted_scores = scores[["importance", metric]].sort_values(by=["importance", metric])
    sorted_scores = sorted_scores.reset_index().drop("index", axis=1)
    n_c = 0 # This is the concordant count for taus a, b, and c.
    n_d = 0 # This is the discordant count for taus a, b, and c.
    n_c_d = 0 # This is the concordant count is for tau d only.
    n_d_d = 0 # This is the discordant count is for tau d only.
    for index_i, row_i in sorted_scores.iterrows():
        # Because data is ordered, there is no need to go through all rows, just the rows from the
        # current one.
        for index_j, row_j in sorted_scores.loc[index_i:].iterrows():
            # These conditional statements take advantage of the fact that the data is ordered.
            if row_i["importance"] < row_j["importance"] and row_i[metric] < row_j[metric]:
                n_c += 1
            elif row_i["importance"] != row_j["importance"] and row_i[metric] != row_j[metric]:
                n_d += 1
            if row_i[metric] < row_j[metric]:
                n_c_d += 1
            elif row_i[metric] > row_j[metric]:
                n_d_d += 1
    # Variables to plug into the tau formulae are defined here.
    r = sorted_scores.shape[0]
    c = sorted_scores.shape[1]
    t = sorted_scores["importance"].value_counts()
    u = sorted_scores[metric].value_counts()
    n_0 = r*(r-1)/2
    n_1 = sorted_scores["importance"].apply(lambda importance: importance*(importance-1)/2).sum()
    n_2 = sorted_scores[metric].apply(lambda centrality: centrality*(centrality-1)/2).sum()
    m = min(r, c)
    # The formulae for the tau values is applied here and the coefficients dictionary is updated.
    tau_a = (n_c-n_d)/n_0
    tau_b = (n_c-n_d)/sqrt((n_0-n_1)*(n_0-n_2))
    tau_c = 2*(n_c-n_d)/((r**2)*((m-1)/m))
    tau_d = (n_c_d-n_d_d)/n_0
    coefficients["tau_a"] = tau_a
    coefficients["tau_b"] = tau_b
    coefficients["tau_c"] = tau_c
    coefficients["tau_d"] = tau_d
    return coefficients

"""
An adaptation of Kendels tau metric called tau x is computed here which handles ties better. More
information can be found in the paper "A New Rank Correlation Coefficient with Appication to the
Consensus Ranking Problem" by Edmond and Maso.
"""
def calculate_tau_x(metric):
    numerator = 0
    for index_i, row_i in scores.iterrows():
        for index_j, row_j in scores.iterrows():
            if index_i != index_j:
                if row_i["importance"] < row_j["importance"]:
                    a = 1
                else:
                    a = -1 # Ties are scored unlike with Kendals approach.
                if row_i[metric] < row_j[metric]:
                    b = 1
                else:
                    b = -1 # Ties are scored unlike with Kendals approach.
                numerator += a*b
    denominator = len(scores)*(len(scores)-1)
    tau_x = numerator/denominator
    return tau_x

# Restults are plotted and printed
def display_results(x, y, title, coefficients, ylim=0):
    print(results)
    plt.scatter(x, y)
    plt.title(title)
    plt.ylim = 0.01 if ylim > 0
    plt.show()

# Read centrality scores into a csv and calculate and display correlations with importance
scores = pd.read_csv("..//data//echr//centrality.csv").drop("Unnamed: 0", axis=1)
x = scores["importance"]
for metric, y in scores.loc[:, ~scores.columns.isin(["importance", "ecli"])].iteritems():
    coefficients = calculate_kendal_rank_correlation_coefficients(metric)
    coefficients["tau_x"] = calculate_adapted_kendal_rank_correlation_coefficient(metric)
    display_results(x, y, title, coefficients)

