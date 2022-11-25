import sys
import json
import argparse
from os.path import dirname, abspath, basename

import pandas as pd
import numpy as np
from collections import Counter

sys.path.append(dirname(dirname(abspath(__file__)))) # This allows imports from another folder.
from definitions.storage_handler import CSV_ECHR_NODES, CSV_ECHR_EDGES, \
                                        JSON_ECHR_NODES, JSON_ECHR_EDGES, \
                                        CSV_ECHR_CENTRALITIES

def calculate_in_degree(nodes, edges):
    """
    The in degree is added to the dataframe by counting occurences in the edges list.
    :param nodes: dataframe cases as nodes of a graph
    :param edges: dataframe links between cases as edges of a graph
    """
    in_degrees = np.zeros(nodes.shape[0])
    index = 0
    for ecli in nodes["ecli"]:
        references = edges.loc[edges["ecli"] == ecli, "references"].values
        if len(references) != 0:
            in_degrees[index] = len(references[0])
        else:
            in_degrees[index] = 0
        index += 1
    nodes["in degree"] = in_degrees

def calculate_out_degree(nodes, edges):
    """
    The out degree is added to the dataframe by counting occurences in the edges list.
    :param nodes: dataframe cases as nodes of a graph
    :param edges: dataframe links between cases as edges of a graph
    """
    out_degrees = np.zeros(nodes.shape[0])
    edge_occurences = pd.Series([x for _list in edges["references"] for x in _list]).value_counts()
    for ecli in nodes["ecli"]:
        if ecli in edge_occurences.index:
            index = nodes.loc[nodes["ecli"] == ecli].index[0]
            out_degrees[index] = edge_occurences[ecli]
    nodes["out degree"] = out_degrees

def calculate_degree(nodes):
    """
    The degree sum is calculated by summing the already calculated in degree and out degree columns.
    :param nodes: dataframe cases as nodes of a graph
    """
    nodes["degree"] = nodes["in degree"]+nodes["out degree"]

def calculate_relative_degree(nodes, isin):
    """
    Depending on isin, the relative in degree or the relative out degree is added to the dataframe 
    by dividing the already existing columns by each other.
    :param nodes: dataframe cases as nodes of a graph
    :param isin: boolean whether to calculate relative in degree of relative out degree
    """
    numerator = nodes["in degree"] if isin else nodes["out degree"]
    denominator = nodes["out degree"] if isin else nodes["in degree"]
    relative_degree = numerator/denominator
    relative_degree.replace([np.inf], numerator.max(), inplace=True)
    column_name = "relative in degree" if isin else "relative out degree"
    nodes[column_name] = relative_degree

def calculate_page_rank(nodes, edges, iterations=100, replace_missing_with_mean=True):
    """
    Page ranks are stored in a new array until all values have been calculated each iteration and
    are finally added to the dataframe.
    :param nodes: dataframe cases as nodes of a graph
    :param edges: dataframe links between cases as edges of a graph
    :param iterations: integer number of iterations for the page rank algorithm
    :param replace_missing_with_true: boolean whether to replace missing nodes' page ranks with the 
                                      mean page rank or with 0
    """
    old_page_ranks = np.full((nodes.shape[0]), 1/nodes.shape[0])
    new_page_ranks = np.zeros(nodes.shape[0])
    reference_counts = pd.Series([x for _list in edges["references"] for x in _list]).value_counts()
    for iteration in range(iterations):
        for ecli in nodes["ecli"]:
            node_index = nodes.loc[nodes["ecli"] == ecli].index
            references = edges.loc[edges["ecli"] == ecli, "references"].values
            # Nodes present in the nodes list but not the edges list are ignored.
            references = [] if len(references) == 0 else references[0]
            # A portion of each incoming node's score updates the page rank.
            for ecli_in in references:
                in_node_index = nodes.loc[nodes["ecli"] == ecli_in].index
                numerator = old_page_ranks[in_node_index]
                # If a referenced case is not in the nodes list then its page rank contribution is
                # taken as the mean of all page ranks or as zero.
                if numerator.size == 0:
                    if replace_missing_with_mean:
                        numerator = np.mean(old_page_ranks)
                    else:
                        numerator = 0
                denominator = nodes.loc[nodes["ecli"] == ecli_in, "out degree"].values
                # If a referenced case is not in the nodes list then its out degree is calculated
                # here.
                if denominator.size == 0:
                    denominator = reference_counts[ecli_in]
                else:
                    denominator = denominator[0]
                new_page_ranks[node_index] += numerator/denominator
        # Page ranks are corrected to be a probability distribution.
        correction = (1-np.sum(new_page_ranks))/new_page_ranks.shape[0]
        new_page_ranks = [element+correction for element in new_page_ranks]
        old_page_ranks = np.copy(new_page_ranks)
        new_page_ranks = np.zeros(old_page_ranks.shape[0])
    nodes["page rank"] = old_page_ranks

def calculate_hits(nodes, edges, iterations=100, replace_missing_with_mean=True):
    """
    Hub and authority scores are updated for each node each iteration and are finally added to the
    dataframe.
    :param nodes: dataframe cases as nodes of a graph
    :param edges: dataframe links between cases as edges of a graph
    :param iterations: integer number of iterations for the hits algorithm
    :param replace_missing_with_true: boolean whether to replace missing nodes' hits with the mean
                                      page rank or with 0
    """
    old_hubs = np.ones(nodes.shape[0])
    old_authorities = np.ones(nodes.shape[0])
    new_hubs = np.zeros(nodes.shape[0])
    new_authorities = np.zeros(nodes.shape[0])
    for iteration in range(iterations):
        for ecli in nodes["ecli"]:
            node_index = nodes.loc[nodes["ecli"] == ecli].index
            # Hub scores of the incoming links are summed to compute the authority score.
            links_in = edges.loc[edges["ecli"] == ecli, "references"].values
            # Nodes present in the nodes list but not the edges list are ignored.
            links_in = [] if len(links_in) == 0 else links_in[0]
            for link in links_in:
                link_index = nodes.loc[nodes["ecli"] == link].index
                # Hub score contributions of missing nodes are optionally replaced with the mean hub 
                # score. 
                if link_index.size == 0 and replace_missing_with_mean:
                    new_authorities[node_index] += np.mean(old_hubs)
                else:
                    new_authorities[node_index] += old_hubs[link_index]
            # Authority scores of outgoing links are summed to compute the hub score.
            for link_index in edges.index:
                if ecli in edges["references"][link_index]:
                    new_hubs[node_index] += old_authorities[link_index]
        # Scores are normalised.
        hub_min = np.min(new_hubs)
        hub_range = np.max(new_hubs)-hub_min
        authority_min = np.min(new_authorities)
        authority_range = np.max(new_authorities)-authority_min
        for index in range(len(new_hubs)):
            if new_hubs.max() > 1:
                new_hubs[index] = (new_hubs[index]-hub_min)/hub_range
            if new_authorities.max() > 1:
                new_authorities[index] = (new_authorities[index]-authority_min)/authority_range
        old_hubs = np.copy(new_hubs)
        old_authorities = np.copy(new_authorities)
        new_hubs = np.zeros(nodes.shape[0])
        new_authorities = np.zeros(nodes.shape[0])
    nodes["hub"] = old_hubs
    nodes["authority"] = old_authorities
    nodes["hits"] = nodes["hub"]+nodes["authority"]

def normalise(nodes, exceptions=["ecli", "importance", "hub", "authority"]):
    """
    Each column is normalised unless included in the exceptions list, which is to save unnecissary
    computation time on columns which are normalised as part of their metric.
    :param nodes: dataframe cases as nodes of a graph
    :param exceptions: list columns not to normalise
    """
    column_names = nodes.columns.values.tolist()
    [column_names.remove(exception) for exception in exceptions]
    for column_name in column_names:
        column = nodes[column_name]
        nodes[column_name] = ((column-column.min())/(column.max()-column.min()))

# The number of nodes, the number of edges, and the density is calculated and displayed.
def calculate_network_statistics(nodes):
    """
    The number of nodes, the number of edges, and the density are calculated and displayed.
    :param nodes: cases as nodes of a graph
    """
    num_nodes = nodes.shape[0]
    num_edges = nodes["in degree"].sum()
    density = num_edges/(num_nodes*(num_nodes-1))
    print(f"nodes:   {num_nodes}")
    print(f"edges:   {num_edges}")
    print(f"density: {density}")

# Script arguments are defined.
parser = argparse.ArgumentParser()
parser.add_argument("--type", help="The type of file to read data from.", type=str, required=False)
args = parser.parse_args()

"""
Nodes and edges lists are read into dataframes. By default, they are taken from json format
with the option to be taken from csv format.
"""
if args.type == "csv":
    nodes = pd.read_csv(CSV_ECHR_CASES_NODES)[["ecli", "importance"]]
    edges = pd.read_csv(CSV_ECHR_CASES_EDGES)
    edges["references"] = edges["references"].apply(eval) # Convert strings to lists
else:
    nodes = pd.DataFrame.from_dict(pd.json_normalize(json.load(open(JSON_ECHR_NODES))),
                                   orient="columns")[["ecli", "importance"]]
    edges = pd.DataFrame.from_dict(pd.json_normalize(json.load(open(JSON_ECHR_EDGES))),
                                   orient="columns")

calculate_in_degree(nodes, edges) # Append in degree to the nodes dataframe.
calculate_out_degree(nodes, edges) # Append out degree to the nodes dataframe.
calculate_degree(nodes) # Append degree sum to the nodes dataframe.
calculate_relative_degree(nodes, True) # Append relative in degree to the nodes dataframe.
calculate_relative_degree(nodes, False) # Append relative out degree to the nodes dataframe.
calculate_page_rank(nodes, edges) # Append page rank to the nodes dataframe.
calculate_hits(nodes, edges) # Append hits to the nodes dataframe.
calculate_network_statistics(nodes) # Display network statistics.
normalise(nodes) # Normalise the columns of the dataframe.

# Results are written to a csv file.
nodes.to_csv(CSV_ECHR_CENTRALITIES, index=False)
