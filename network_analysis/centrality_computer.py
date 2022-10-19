from os.path import dirname, abspath, basename
import sys

import pandas as pd
import numpy as np
from collections import Counter

sys.path.append(dirname(dirname(abspath(__file__)))) # This is to allow the import from a file from another folder.
from definitions.storage_handler import DIR_ECHR

# Depending on isin, the in degree or out degree is added to the dataframe by counting occurences in
# the edges list.
def calculate_degree(nodes, edges, isin):
    links = edges["ecli2"].tolist() if isin else edges["ecli1"].tolist()
    frequencies = dict(Counter(link for link in links))
    degrees = np.zeros(nodes.shape[0])
    for index in range(nodes.shape[0]):
        ecli = nodes["ecli"].loc[[index]].values[0]
        if ecli in frequencies:
            degrees[index] = frequencies[ecli]
    column_name = "in degree" if isin else "out degree"
    nodes[column_name] = degrees

# Depending on isin, the relative in degree or the relative out degree is added to the dataframe by 
# dividing the already existing columns by each other.
def calculate_relative_degree(nodes, isin):
    numerator = nodes["in degree"] if isin else nodes["out degree"]
    denominator = nodes["out degree"] if isin else nodes["in degree"]
    relative_degree = numerator/denominator
    relative_degree.replace([np.inf], numerator.max(), inplace=True)
    column_name = "relative in degree" if isin else "relative out degree"
    nodes[column_name] = relative_degree

# The degree sum is calculated by summing the already calculated in degree and out degree columns.
def calculate_degree_sum(nodes):
    nodes["degree sum"] = nodes["in degree"]+nodes["out degree"]

# Page ranks are stored in a new array until all values have been calculated each iteration and
# are finally added to the dataframe.
def calculate_page_rank(nodes, edges, iterations=100):
    old_page_ranks = np.full((nodes.shape[0]), 1/nodes.shape[0])
    new_page_ranks = np.zeros(old_page_ranks.shape[0])
    for iteration in range(iterations): 
        for ecli in nodes["ecli"]:
            node_index = nodes.loc[nodes["ecli"] == ecli].index
            for ecli_in in edges.loc[edges["ecli2"] == ecli, "ecli1"]:
                num_out = edges["ecli1"].value_counts()[ecli_in]
                indexes_in = nodes.loc[nodes["ecli"] == ecli_in].index.values
                if len(indexes_in) > 0:
                    link_in_index = indexes_in[0]
                    page_rank_out = old_page_ranks[link_in_index]
                    new_page_ranks[node_index] += page_rank_out/num_out
        correction = (1-np.sum(new_page_ranks))/new_page_ranks.shape[0]
        new_page_ranks = [element+correction for element in new_page_ranks]
        old_page_ranks = np.copy(new_page_ranks)
        new_page_ranks = np.zeros(old_page_ranks.shape[0])
    nodes["page rank"] = old_page_ranks

# Hub and authority scores are updated for each node each iteration and are finally added to the
# dataframe.
def calculate_hits(nodes, edges, iterations=100):
    nodes["hub"] = 1.0
    nodes["authority"] = 1.0
    for iteration in range(iterations):
        for ecli in nodes["ecli"]:
            links_in = edges.loc[edges["ecli2"] == ecli, "ecli1"]
            nodes.loc[nodes["ecli"] == ecli, "authority"] = (
            nodes.loc[nodes.apply(lambda x: x["ecli"] in links_in.values, axis=1), "hub"].sum()
            )
        for ecli in nodes["ecli"]:
            links_out = edges.loc[edges["ecli1"] == ecli, "ecli2"]
            nodes.loc[nodes["ecli"] == ecli, "hub"] = (
            nodes.loc[nodes.apply(lambda x: x["ecli"] in links_out.values, axis=1), 
                                  "authority"].sum()
            )
        nodes["authority"] = ((nodes["authority"]-nodes["authority"].min())
                             /(nodes["authority"].max()-nodes["authority"].min()))
        nodes["hub"] = (nodes["hub"]-nodes["hub"].min())/(nodes["hub"].max()-nodes["hub"].min())

# Each column is normalised unless included in the exceptions list, which is to save unnecissary
# computation time on columns which are normalised as part of their metric.
def normalise(nodes, exceptions=["ecli", "importance"]):
    column_names = nodes.columns.values.tolist()
    [column_names.remove(exception) for exception in exceptions]
    for column_name in column_names:
        column = nodes[column_name]
        nodes[column_name] = ((column-column.min())/(column.max()-column.min()))

# Nodes and edges lists are read into dataframes.
nodes = pd.read_csv("\\".join((DIR_ECHR, "ECHR_nodes.csv")))[["ecli", "importance"]]
edges = pd.read_csv("\\".join((DIR_ECHR, "ECHR_edges.csv")))

calculate_degree(nodes, edges, True) # Append in degree to the nodes dataframe.
calculate_degree(nodes, edges, False) # Append out degree to the nodes dataframe.
calculate_degree_sum(nodes) # Append degree sum to the nodes dataframe
calculate_relative_degree(nodes, True) # Append relative in degree to the nodes dataframe.
calculate_relative_degree(nodes, False) # Append relative out degree to the nodes dataframe.
calculate_page_rank(nodes, edges) # Append page rank to the nodes dataframe.
calculate_hits(nodes, edges) # Append hits to the nodes dataframe.
normalise(nodes) # Normalise the columns of the dataframe.

# Results are written to a csv file.
nodes.to_csv("\\".join((DIR_ECHR, "centrality.csv")))
