import sys
import numpy as np
import pandas as pd
from math import sqrt
from os.path import dirname, abspath

import matplotlib.pyplot as plt

sys.path.append(dirname(dirname(abspath(__file__)))) # Allow imports from another folder.
from definitions.storage_handler import CSV_ECHR_CASES_CENTRALITIES

def calculate_kendal_taus(scores):
    """
    Four Kendal rank coefficients, a, b, c, and a custom one d, are calculated in the same function
    so that the concordant and discordant counts can be used for multiple metrics without needing to
    repeat the loop. Separating these would reduce efficiancy significantly and and there is no
    noticable slowdown when computing all four even when only one is necissary.
    :param scores: dataframe importance and scores for a centrality metric
    """
    coefficients = {}
    sorted_scores = scores.sort_values(by=["importance", "metric"])
    sorted_scores = sorted_scores.reset_index().drop("index", axis=1)
    n_c = 0 # This is the concordant count for taus a, b, and c.
    n_d = 0 # This is the discordant count for taus a, b, and c.
    n_c_d = 0 # This is the concordant count is for tau d only.
    n_d_d = 0 # This is the discordant count is for tau d only.
    n_1 = 0 # This is a variable which depends on the number of ties in importance.
    n_2 = 0 # This is a variable which depends on the number of ties in the metric.
    tie_counter_1 = 0 # This will update n_1.
    tie_counter_2 = 0 # This will update n_2.
    for index_i, row_i in sorted_scores.iterrows():
        # Because data is ordered, there is no need to go through all rows, just the rows from the
        # current one.
        for index_j, row_j in sorted_scores.loc[index_i:].iterrows():
            # These conditional statements take advantage of the fact that the data is ordered.
            if row_i["importance"] < row_j["importance"] and row_i["metric"] < row_j["metric"]:
                n_c += 1
            elif row_i["importance"] != row_j["importance"] and row_i["metric"] != row_j["metric"]:
                n_d += 1
            if row_i["metric"] < row_j["metric"]:
                n_c_d += 1
            elif row_i["metric"] > row_j["metric"]:
                n_d_d += 1
        if index_i != 0:
            prev_importance = sorted_scores.loc[index_i-1]["importance"]
            if row_i["importance"] == prev_importance:
                tie_counter_1 += 1
            if row_i["importance"] != prev_importance or index_i == sorted_scores.shape[0]:
                n_1 += (tie_counter_1*(tie_counter_1-1))/2
                tie_counter_1 = 0
            prev_metric = sorted_scores.loc[index_i-1]["metric"]
            if row_i["metric"] == prev_metric:
                n_2 += 1
            if row_i["metric"] != prev_metric or index_i == sorted_scores.shape[0]:
                n_2 += (tie_counter_2*(tie_counter_2-1))/2
    # Variables to plug into the tau formulae are defined here.
    r = sorted_scores.shape[0]
    c = sorted_scores.shape[1]
    t = sorted_scores["importance"].value_counts()
    u = sorted_scores["metric"].value_counts()
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

def calculate_tau_x(scores):
    """
    An adaptation of Kendels tau metric called tau x is computed here which handles ties better. More
    information can be found in the paper "A New Rank Correlation Coefficient with Appication to the
    Consensus Ranking Problem" by Edmond and Maso.
    :param scores: dataframe importance and scores for a centrality metric
    """
    numerator = 0
    for index_i, row_i in scores.iterrows():
        for index_j, row_j in scores.iterrows():
            if row_i["importance"] > row_j["importance"]:
                a = -1
            else:
                a = 1 # Ties are scored unlike with Kendals approach.
            if row_i["metric"] > row_j["metric"]:
                b = -1
            else:
                b = 1 # Ties are scored unlike with Kendals approach.
            numerator -= a*b
    denominator = len(scores)*(len(scores)-1)
    tau_x = numerator/denominator
    return tau_x

def calculate_spearman_rho(scores):
    """
    Spearmans rank correlation coefficient is computed here.
    :param scores: dataframe importance and scores for a centrality metric
    """    
    scores["importance rank"] = scores["importance"].rank() # Default ranking is used dues to ties.
    scores["metric rank"] = scores["metric"].rank() # Default ranking is used due to ties.
    scores["difference squared"] = (scores["importance rank"]-scores["metric rank"])**2
    numerator = 6*(scores["difference squared"].sum())
    denominator = scores.shape[0]*(scores.shape[0]**2-1)
    rho = 1-(numerator/denominator)
    return rho

def remove_outliers(df, stds=5):
    """
    Ourliers are removed when they are outside of a given number of standard deviations.
    :param: df data rows to potentially remove based on outlier detection in the second column
    """
    mean = df.iloc[:, 1].mean()
    sd = df.iloc[:, 1].std()
    df = df[(df.iloc[:, 1] < mean+(stds*sd))]
    return df

def display_results(metric, x_1, y_1, coefficients_1, x_2, y_2, coefficients_2):
    """
    Results are plotted and printed.
    :param: metric: string centrality metric
    :param: x_1 series importances before outlier removal
    :param: y_1 series scores for a centrality metric before outlier removal
    :coefficients_1: correlation coefficients before outlier removal
    :param: x_2 series importances after outlier removal
    :param: y_2 series scores for a centrality metric after outlier removal
    :coefficients_2: correlation coefficients after outlier removal
    """
    print(metric)
    print("correlation coefficients with outliers:    ", coefficients_1)
    print("correlation coefficients without outliers: ", coefficients_2)  
    fig, (ax_1, ax_2) = plt.subplots(1, 2)
    fig.suptitle(metric)
    ax_1.scatter(x_1, y_1)
    ax_2.scatter(x_2, y_2)
    #plt.show()

# Read centrality scores into a csv and calculate and display correlations with importance.
df = pd.read_csv(CSV_ECHR_CASES_CENTRALITIES).drop("Unnamed: 0", axis=1).fillna(0)
x_1 = df["importance"]
for metric, y_1 in df.loc[:, ~df.columns.isin(["importance", "ecli"])].iteritems():
    scores = pd.concat([x_1, y_1], axis=1)
    scores.columns = ["importance", "metric"]
    coefficients_1 = calculate_kendal_taus(scores)
    coefficients_1["tau_x"] = calculate_tau_x(scores)
    coefficients_1["rho"] = calculate_spearman_rho(scores)
    without_outliers = remove_outliers(scores)
    x_2 = without_outliers.iloc[:, 0]
    y_2 = without_outliers.iloc[:, 1]
    scores = pd.concat([x_2, y_2], axis=1)
    scores.columns = ["importance", "metric"]
    coefficients_2 = calculate_kendal_taus(scores)
    coefficients_2["tau_x"] = calculate_tau_x(scores)
    coefficients_2["rho"] = calculate_spearman_rho(scores)
    display_results(metric, x_1, y_1, coefficients_1, x_2, y_2, coefficients_2)
