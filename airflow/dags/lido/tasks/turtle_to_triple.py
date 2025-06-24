from airflow import DAG
from airflow.operators.bash import BashOperator

from lido.config import *

def task_make_laws_nt(dag: DAG) -> BashOperator:
    """
    Convert turtle to triples and fitler laws and their relevant predicates.
    Then sort on first column to ensure subjects are grouped
    """

    FILTER_SUBJECT = '<http://linkeddata.overheid.nl/terms/bwb/id/'
    FILTER_PREDICATES = [
        "<http://purl.org/dc/terms/identifier>",
        "<http://purl.org/dc/terms/type>",
        "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>",
        "<http://linkeddata.overheid.nl/terms/isOnderdeelVan>",
        "<http://linkeddata.overheid.nl/terms/isOnderdeelVanRegeling>",
        "<http://purl.org/dc/terms/title>",
        "<http://www.w3.org/2004/02/skos/core#prefLabel>",
        "<http://www.w3.org/2000/01/rdf-schema#label>",
        "<http://linkeddata.overheid.nl/terms/heeftJuriconnect>",
        "<http://linkeddata.overheid.nl/terms/heeftOnderdeelNummer>"
    ]
    
    FILTER_PREDICATES_CMD = ' '.join(list(map(lambda p: f'-e "{p}"', FILTER_PREDICATES)))

    return BashOperator(
        task_id='make_laws_nt',
        bash_command=(
            f'zcat {FILE_LIDO_TTL_GZ} '
            f'| serdi -l -i turtle -o ntriples - '
            f'| grep "^{FILTER_SUBJECT}" '
            f'| fgrep {FILTER_PREDICATES_CMD} '
            f'| sort -k1,1 '
            f'> {FILE_LAWS_NT}'
        ),
        dag=dag,
    )

def task_make_cases_nt(dag: DAG) -> BashOperator:
    """
    Convert turtle to triples and fitler cases and their relevant predicates.
    Then sort on first column to ensure subjects are grouped
    """

    FILTER_SUBJECT = '^<http://linkeddata.overheid.nl/terms/jurisprudentie/id/'
    FILTER_PREDICATES = [
        "<http://purl.org/dc/terms/identifier>",
        "<http://purl.org/dc/terms/type>",
        "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>",
        "<http://purl.org/dc/terms/title>",
        "<http://www.w3.org/2004/02/skos/core#prefLabel>",
        "<http://www.w3.org/2000/01/rdf-schema#label>",
        "<http://linkeddata.overheid.nl/terms/refereertAan>",
        "<http://linkeddata.overheid.nl/terms/linkt>",
        "<http://linkeddata.overheid.nl/terms/heeftZaaknummer>",
        "<http://linkeddata.overheid.nl/terms/heeftUitspraakdatum>"
    ]

    FILTER_PREDICATES_CMD = ' '.join(list(map(lambda p: f'-e "{p}"', FILTER_PREDICATES)))
    
    return BashOperator(
        task_id='make_cases_nt',
        bash_command=(
            f'zcat {FILE_LIDO_TTL_GZ} '
            f'| serdi -l -i turtle -o ntriples - '
            f'| grep "^{FILTER_SUBJECT}" '
            f'| fgrep {FILTER_PREDICATES_CMD} '
            f'| sort -k1,1 '
            f'> {FILE_CASES_NT}'
        ),
        dag=dag,
    )
