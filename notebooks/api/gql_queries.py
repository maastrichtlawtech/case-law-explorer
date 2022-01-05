from definitions.terminology.attribute_values import Domain, Instance, DataSource, DocType
from enum import Enum
import json


class AttributesList(Enum):
    ID = 'ID'                       # node ID attribute (ecli)
    ALL = 'ALL'                     # all attributes as displayed in the app
    QUERYHANDLER = 'QUERYHANDLER'   # attributes required for querying a network
    NETWORKSTATS = 'NETWORKSTATS'   # attributes required for the computation of the network statistics


def gql_query_network(
        attributes_to_fetch: AttributesList = AttributesList.QUERYHANDLER,
        data_sources: [DataSource] = [DataSource.RS],
        eclis: str = '',
        keywords: str = '',
        articles: str = '',
        date_start='1900-01-01',
        date_end='2021-12-12',
        instances: [Instance] = [],
        domains: [Domain] = [],
        doc_types: [DocType] = [DocType.DEC],
        degrees_sources: int = 0,
        degrees_targets: int = 1
):
    if eclis == '' and keywords == '' and articles == '' \
            and instances == [] and domains == []:
        print('Please select at least one of: eclis, keywords, articles, instances, domains')
        return None
    instances_flat = []
    for instance in instances:
        print(instance.value)
        if type(instance.value) is list:
            print('is list')
            for i in instance.value:
                instances_flat.append(i)
        else:
            instances_flat.append(instance.value)

    return f'''
    query MyQuery {{
      queryNetworkByUserInput(
        attributesToFetch: {attributes_to_fetch.value},
        DataSources: {[data_source.value for data_source in data_sources]},
        DateEnd: "{date_end}",
        DateStart: "{date_start}",
        DegreesSources: {degrees_sources},
        DegreesTargets: {degrees_targets},
        Doctypes: {[doc_type.value for doc_type in doc_types]},
        Articles: "{articles}",
        Domains: {json.dumps([domain.value for domain in domains])},
        Eclis: "{eclis}",
        Instances: {json.dumps(instances_flat)},
        Keywords: "{keywords}") {{
        message
        edges {{
          id
          source
          target
        }}
        nodes {{
          id
          data
        }}
      }}
    }}
    '''


def gql_fetch_node_data(node: dict, attributes_to_fetch: AttributesList = AttributesList.ALL):
    query_string = f"""
    query MyQuery {{
      fetchNodeData(node: {json.dumps(node)}, attributesToFetch: {attributes_to_fetch.value}) {{
        data
        id
      }}
    }}
    """
    query_string = query_string.replace('"id"', 'id')
    query_string = query_string.replace('"data"', 'data')
    return query_string


def gql_batch_fetch_node_data(nodes: [dict], attributes_to_fetch: AttributesList = AttributesList.ALL):
    query_string = f"""
    query MyQuery {{
      batchFetchNodeData(
        attributesToFetch: {attributes_to_fetch.value},
        nodes: {json.dumps(nodes)}
        ) {{
        data
        id
      }}
    }}
    """
    query_string = query_string.replace('"id"', 'id')
    query_string = query_string.replace('"data"', 'data')
    return query_string


def gql_compute_networkstatistics(nodes: [dict], edges: [dict]):
    query_string = f"""
    query MyQuery {{
      computeNetworkStatistics(edges: {json.dumps(edges)}, nodes: {json.dumps(nodes)})
    }}
    """
    query_string = query_string.replace('"id"', 'id')
    query_string = query_string.replace('"data"', 'data')
    query_string = query_string.replace('"source"', 'source')
    query_string = query_string.replace('"target"', 'target')
    return query_string
