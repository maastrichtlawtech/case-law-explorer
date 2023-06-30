# Data extraction

This walkthrough will teach you how to locally extract data from the defined sources, 
transform it to be clean and in unified format, and optionally load it to an AWS DynamoDB database.
For more information about the data sources and the format of the extracted data see [Datasets](/datasets/).

## Setup

> [!WARNING|label:Pre-requirements]
> - [Python 3.7](https://www.python.org/downloads/release/python-379/) or newer
> - [pip 21.3](https://pip.pypa.io/en/stable/news/#v21-3) or newer

Clone the [maastrichtlawtech/case-law-explorer](https://github.com/maastrichtlawtech/case-law-explorer) project.

```bash
$ git clone https://github.com/maastrichtlawtech/case-law-explorer
```

Install the required Python packages.

```bash
$ pip install -r requirements.txt
```

### Environment variables

Create the environmental variables into the `.env` file, as suggested in [`.env.example` file](https://raw.githubusercontent.com/maastrichtlawtech/case-law-explorer/master/.env.example). The following variables are used in the Caselaw extraction (see explanation below):

```.env.example
AIRFLOW_UID=5000
URL_RS_ARCHIVE=http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip

# The variables below are used to setup the AWS databases
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
AWS_DEFAULT_REGION=

DDB_TABLE_NAME=caselawexplorer-test
DDB_TABLE_NAME_CELEX=caselawexplorer-celex-test
DDB_NAME_ECHR=caselawexplorer-echr-test
S3_BUCKET_NAME=caselawexplorer-load-test
CELLAR_NODES_BUCKET_NAME=cellar-nodes-edges-bucket

APPSYNC_ENDPOINT=appsync-endpoint-here
COGNITO_USER_KEY=my-user-key-here
COGNITO_CLIENT_ID=client-secret-here

LIDO_ENDPOINT=http://linkeddata.overheid.nl/service/get-links
LIDO_USERNAME=lido-username-here
LIDO_PASSWORD=lido-pw-here

# The links below are pointing to eurlex websites containing specific metadata
# They have a "cIdHere" - it is a place where you put the CELEX ID of a case.
# If they were to be changed later on, the celex substitute should be put in place of the CELEX ID
CELEX_SUBSTITUTE=cIdHere
EURLEX_SUMMARY_LINK_INF=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere&from=EN
EURLEX_SUMMARY_LINK=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere_SUM&from=EN
EURLEX_SUMJURE_LINK=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=URISERV:cIdHere_SUMJURE&from=EN
EURLEX_ALL_DATA=https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:cIdHere
EURLEX_FULL_TEXT=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere&from=EN

# The following variables are used to extract citations via the cellar-extractor library
EURLEX_WEBSERVICE_USERNAME=
EURLEX_WEBSERVICE_PASSWORD=

RS_SETUP=True
```
### Storage location
Read more about the [`Storage` object](/reference/storage). 

In the storage location, the data directory follows the structure of:
<pre>
 
└── data
    ├── processed <i># processed data as result of the transformation scripts</i>
    ├── raw <i># extracted data as result of the extractions scripts</i>
    └── full_text <i># full text data for Cellar and ECHR cases </i>

</pre>


## Extract

This walkthrough will extract data from the defined [datasets](/datasets/) into the local storage.
If you wish to eventually load the processed data into an AWS DynamoDB database, please first follow our guide on [setting up AWS](/graphql/?id=setup-aws).

### Rechtspraak data

The [Rechtspraak extractor script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader.py) 
downloads the metadata of Dutch Court cases available at 
[https://data.rechtspraak.nl/Uitspraken](https://data.rechtspraak.nl/Uitspraken) to `data/raw/RS_cases.csv`. 



```bash
$ python3 airflow/dags/data_extraction/caselaw/rechtspraak/rechtspraak_extraction.py
```

**Options:**
- `amount` (int): number of documents to retrieve
- `starting_date` (YYYY-MM-DD): Last modification date to look forward from
- `ending_date` (YYYY-MM-DD): Last modification date to look back from

**Output:**
- `data/raw/RS_cases.csv`
---
**Functionality:**
- Uses the rechtspraak-extractor to download the meta-data of cases 
- A detailed functionality description is available at the library page of [rechtspraak-extractor](https://pypi.org/project/rechtspraak-extractor/).

### ECHR data

The [ECHR harvester script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/echr/ECHR_metadata_harvester.py) 
extracts all cases from HUDOC.

```bash
$ python3 airflow/dags/data_extraction/caselaw/echr/echr_extraction.py
```
**Options:**
- `start-id` (int): id of the first case to be downloaded
- `end-id` (int): id of the last case to be downloaded
- `count` (int): number of documents to retrieve
- `start-date` (YYYY-MM-DD): last modification date to look forward from
- `end-date` (YYYY-MM-DD): last modification date to look back from
- `skip-missing-dates` (bool): decides whether to skip cases with missing dates
- `fields` (list): list of fields to be collected by the extractor
- `fresh` (bool): flag for running a complete download
- `language` (list): list of languages to be extracted

**Output:**
- `data/raw/ECHR_metadata.csv`

**Functionality:**
- Builds the query URL with the endpoint http://hudoc.echr.coe.int/app/query/, filters such as `contentsitename` or `documentcollectionid2`, and arguments such as `start` and `length`.
- Fetches the data from the API and stores it in a `DataFrame` for each page returned.
- Finally, the data is stored using the [`Storage` object](/reference/storage). 
- A detailed functionality description is available at the library page of [echr-extractor](https://pypi.org/project/echr-extractor/).

### CJEU data

The [cellar extraction script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/cellar/cellar_extraction.py) 
extracts cases from the CELLAR database.

```bash
$ python3 airflow/dags/data_extraction/caselaw/cellar/cellar_extraction.py 
```
**Options:**
- `--amount` (int): number of documents to retrieve
- `--starting-date` (str): last modification date to look forward from


**Output:**
- `data/raw/cellar_csv_data.csv`
- `data/full_text/cellar_full_text.json`
- `data/processed/cellar_edges.txt`
- `data/processed/cellar_nodes.txt`

**Functionality:**
- It queries SPARQL endpoint https://publications.europa.eu/webapi/rdf/sparql for all the ECLIs available in the CELLAR that are related to the CJEU. 
- For each ECLI returned, it queries the API for the metadata of each case, and stores it in a `DataFrame`. 
- A detailed documentation on the functionalities of the cellar extraction can be found on the library page of the [cellar_extractor](https://pypi.org/project/cellar-extractor/).

## Transform

The [data transformation script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_transformation/data_transformer.py) 
transforms the raw data to a uniform format that matches all the datasets, in order to assure all of them follow the same naming conventions and definitions (see more about the [definitions references](/reference/attribute)).

Transform the data available in the `data/raw/` directory. The processed data is stored in the `data/processed/` directory.

```bash
$ python3 airflow/dags/data_transformation/data_transformer.py 
```

**Input:**  
- `data/raw/cellar_csv_data.csv`
- `data/raw/ECHR_metadata.csv`
- `data/raw/RS_cases.csv`
    
**Output:**  
- `data/processed/cellar_csv_data_clean.csv`
- `data/processed/ECHR_metadata_clean.csv`
- `data/processed/RS_cases_clean.csv`

**Functionality:**
- For each input file: reads input file by row
- Maps each row attribute name to global attribute name (see [attribute reference](/reference/attribute))
- Applies adequate transformation function to each row attribute value (see [utils reference](/reference/utils))
- Writes clean row to output file
- Finally, the data is stored using the [`Storage` object](/reference/storage)

## Load

If you would like to load the data into AWS services instead, please first follow our guide on [setting up AWS](/graphql/?id=setup-aws).
The [data loader script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_loading/data_loader.py) 
loads the data into the DynamoDB table defined in the `.env` file.


```bash
python3 airflow/dags/data_loading/data_loader.py
```

**Input:**  
- `data/processed/cellar_csv_data.csv`
- `data/processed/RS_cases_clean.csv`
- `data/processed/ECHR_metadata_clean.csv`
- `data/full_text/cellar_full_text.json`
- `data/full_text/ECHR_full_text.json`
- `data/processed/cellar_edges.txt`
- `data/processed/cellar_nodes.txt`
- `data/processed/ECHR_edges.txt`
- `data/processed/ECHR_nodes.txt`
    
**Output:**
- `data/processed/DDB_eclis_failed.csv`

**Functionality:**
- For each input file: reads input file by row
- Analyzes row and creates items to put or update in DynamoDB table according to key schema
(see [row_processors reference](reference/row-processors))
- Analyzes row and creates items to index or update in OpenSearch index
([row_processors reference](/reference/row-processors/?id=opensearch-service))
- Loads items to DynamoDB table and/or OpenSearch index as defined in `.env` file
- Writes errors and item keys/item IDs of failed loading attempts to `data/processed/DDB_eclis_failed.csv`
- For each full_text file, uploads separate json files containing full-text information for each ECHR/CELLAR case in the AWS bucket.
- For the nodes and edges for ECHR/CELLAR, it uploads the files onto the nodes-and-edges-bucket or updates the existing files.