import glob, sys
from os.path import dirname, abspath
import pandas as pd
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))
from definitions.storage_handler import DIR_DATA_PROCESSED
from SPARQLWrapper import SPARQLWrapper, JSON


def get_citations(source_celex, cites_depth=1, cited_depth=1):
    """
    Gets all the citations one to X steps away. Hops can be specified as either
    the source document citing another (defined by `cites_depth`) or another document
    citing it (`cited_depth`). Any numbers higher than 1 denote that new source document
    citing a document of its own.

    This specific implementation does not care about intermediate steps, it simply finds
    anything X or fewer hops away without linking those together.
    """
    sparql = SPARQLWrapper('https://publications.europa.eu/webapi/rdf/sparql')
    sparql.setReturnFormat(JSON)
    sparql.setQuery('''
        prefix cdm: <http://publications.europa.eu/ontology/cdm#>
        prefix xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT DISTINCT * WHERE
        {
        {
            SELECT ?name2 WHERE {
                ?doc cdm:resource_legal_id_celex "%s"^^xsd:string .
                ?doc cdm:work_cites_work{1,%i} ?cited .
                ?cited cdm:resource_legal_id_celex ?name2 .
            }
        } UNION {
            SELECT ?name2 WHERE {
                ?doc cdm:resource_legal_id_celex "%s"^^xsd:string .
                ?cited cdm:work_cites_work{1,%i} ?doc .
                ?cited cdm:resource_legal_id_celex ?name2 .
            }
        }
        }''' % (source_celex, cites_depth, source_celex, cited_depth))
    ret = sparql.queryAndConvert()

    targets = set()
    for bind in ret['results']['bindings']:
        target = bind['name2']['value']
        targets.add(target)
    targets = set([el for el in list(targets) ])  # Filters the list. Filtertype: '3'=legislation, '6'=case law.

    return targets
def read_csv(file_path):
    try:
        data = pd.read_csv(file_path,sep=",",encoding='utf-8')
        #print(data)
        return data
    except:
        print("Something went wrong when trying to open the csv file!")
        sys.exit(2)
def add_citations(data):
    name='WORK CITES WORK. CI / CJ'
    citations = data.loc[:,"CELEX IDENTIFIER"]
    citations_column = pd.Series([])
    for i in range(len(citations)):
        citation = get_citations(citations[i])
        if len(citation) !=0:
            citations_column[i]="_".join(citation)
    print(citations_column)
    columns=data.columns
    index=columns.get_loc(name)
    data.drop(columns=[name],axis=1,inplace=True)
    data.insert(index,name,citations_column)

if __name__ == '__main__':
    csv_files = (glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv"))
    print(f"FOUND {len(csv_files)} CSV FILES")
    for i in range(len(csv_files)):
        if ("Extracted" in csv_files[i]):
            print("")
            print(f"EXTRACTING FROM {csv_files[i]} ")
            data = read_csv(csv_files[i])
            add_citations(data)
            data.to_csv(csv_files[i].replace("Extracted","With Citations"), index=False)