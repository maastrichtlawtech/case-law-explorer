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
URL_RS_ARCHIVE=http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip

LI_ENDPOINT=https://api.legalintelligence.com
LI_CLIENT_ID=user@email.here
LI_CLIENT_SECRET=secret-key-here

LIDO_ENDPOINT=http://linkeddata.overheid.nl/service/get-links
LIDO_USERNAME=lido-username-here
LIDO_PASSWORD=lido-pw-here
```
Environment variables used for local caselaw extraction:
- `URL_RS_ARCHIVE` is used in the extraction of the [Rechtspraak archive](/datasets/?id=rechtspraak-archive).
- `LI_` variables are used in the extraction of [Legal Intelligence data](/datasets/?id=legal-intelligence-api). To generate and retrieve the client secret key, log in to [Legal Intelligence](https://www.legalintelligence.com/), go to *User > Instellingen* and click *Aanmaken* under *Persoonlijke gegevens > Secret Key (LI-API)*. For more information, see the [API technical information](https://www.legalintelligence.com/nl/handleidingen/api-technical-information/) of Legal Intelligence.
- `LIDO_` variables are used in the extraction of citations from the [LIDO API](/datasets/?id=linked-data-overheid-lido). One can request a username and password by sending an email to linkeddata@koop.overheid.nl, as per their service documentation.

Remaining environment variables:
- `AWS_`, `DDB_`, `OS_`, and `S3_` variables are used to load the data into the AWS services. They are being used and explained in the [GraphQL API Documentation](/graphql/), and not relevant for this walkthrough.
- `APPSYNC_ENDPOINT` and `COGNITO_` variables are used in the Case Law Explorer developer API demos available in the published [notebooks](https://github.com/maastrichtlawtech/case-law-explorer/tree/master/notebooks/api).

### Storage location

All extraction and transformation scripts are using the `location` argument. Pass `local` or `aws` as location to read the input data from and store the output data to. 
 
When set to `local`, the script reads and writes input and output data to a **locally** generated `data/` directory. 
When set to `aws`, the script reads and writes input and output data to an automatically generated bucket on **AWS S3**.
Read more about the [`Storage` object](/reference/storage). 

In both storage locations, the data directory follows the structure of:
<pre>
 
└── data
    ├── processed <i># processed data as result of the transformation scripts</i>
    ├── raw <i># extracted data as result of the extractions scripts</i>
    └── Rechtspraak <i># data downloaded from Rechtspraak.nl </i>

</pre>

> [!WARNING]
> In both storage locations, data will be overwritten if the same script is called multiple times!

## Extract

This walkthrough will extract data from the defined [datasets](/datasets/) into the local storage.
If you wish to eventually load the processed data into an AWS DynamoDB database and/or store the raw and processed data
in an AWS S3 bucket, please first follow our guide on [setting up AWS](/graphql/?id=setup-aws) and 
set the location argument to `aws` when calling the extraction and transformation scripts.

### Rechtspraak data

The [Rechtspraak downloader script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader.py) 
downloads the latest version of the zipped folder with Rechtspraak data from 
[http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip](http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip) to `data/Rechtspraak/OpenDataUitspraken.zip`. 

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader.py local
```

**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Output:**
- `data/Rechtspraak/OpenDataUitspraken.zip`

---

The [Rechtspraak unzipper script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/rechtspraak/rechtspraak_dump_unzipper.py) 
extracts the raw `.xml` files from the zipped folder and sub-folders in `data/Rechtspraak/OpenDataUitspraken.zip` to `data/Rechtspraak/OpenDataUitspraken/`
and creates an index of all extracted case ECLIs with their respective decision dates.

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_unzipper.py local
```

**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Input:**
- `data/Rechtspraak/OpenDataUitspraken.zip`

**Output:**
- `data/Rechtspraak/OpenDataUitspraken/`
- `data/Rechtspraak/OpenDataUitspraken_index.csv`: *ecli*s and corresponding *date_decision*s

---

The [Rechtspraak parser script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/rechtspraak/rechtspraak_metadata_dump_parser.py) 
parses the `.xml` files from `data/Rechtspraak/OpenDataUitspraken/` into `.csv` files in the `data/raw/` directory
and generates an index of all parsed *ecli*s, *date_decision*s and *predecessor_successor_cases*.

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_metadata_dump_parser.py local
```

**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Input:**
- `data/Rechtspraak/OpenDataUitspraken/`
- `data/Rechtspraak/OpenDataUitspraken_index.csv`

**Output:**
- `data/raw/RS_cases.csv`
- `data/raw/RS_index.csv`: *ecli*s, *date_decision*s and *predecessor_successor_cases*
- `data/raw/RS_opinions.csv`

### Legal Intelligence data

The [Legal Intelligence extrator script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/legal_intelligence/legal_intelligence_extractor.py) 
extracts the Legal Intelligence data available for each case previously extracted from the Rechtspraak archive. The data is stored and merge in the `data/raw/LI_cases.csv` file. 

```bash
$ python3 data_extraction/caselaw/legal_intelligence/legal_intelligence_extractor.py local
```

**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Output:**
- `data/raw/LI_cases.csv`

**Functionality:**
- Builds the query URL using the endpoint https://api.legalintelligence.com/, the query string, and the filters (*e.g.* jurisdiction, court, country).
- Retrieves the data from the URL, cleans it based on a few rules (*e.g.* court duplicates, dates), and stores it a `DataFrame`. It repeats this step for each page returned by the API.
- Finally, it stores the data using the [`Storage` object](/reference/storage). 

### LiDO data

The [citations extractor script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/citations/rechtspraak_citations_extractor_incremental.py) 
extracts the citations provided by the LIDO API for all the available cases previously extracted from the Rechtspraak archive. The data is stored in the `data/raw/caselaw_citations.csv` file (or `legislation`).

```bash
$ python3 data_extraction/citations/rechtspraak_citations_extractor_incremental.py local
```

**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Options:**
- `--failed` (flag): if present, parse list of failed eclis instead of full list of eclis
- `--incoming` (flag): if present, fetch incoming citations instead of outgoing citations

**Input:**
- `data/raw/RS_index.csv` or `data/raw/LIDO_eclis_failed.csv`: table of *ecli*s, *date_decision*s, *predecessor_successor_cases*

**Output:**
- `data/raw/caselaw_citations.csv`
- `data/raw/legislation_citations.csv`
- `data/raw/LIDO_eclis_failed.csv`: *ecli*s, *date_decision*s and *predecessor_successor_cases*

**Functionality:**
- Reads a CSV file with a list of *ecli*s, corresponding *date_decision*s and *predecessor_successor_cases* to be used to search LiDO.
- Builds the LiDO query URL using the API endpoint http://linkeddata.overheid.nl/service/get-links and a few filters such as `start`, `rows`, `output`.
- The responses from the API are being cleaned and stored in a `DataFrame`. This is repeated from all the pages returned by the API. 
- The *ecli*s, *date_decision*s and *predecessor_successor_cases* of failed attempts are written to `data/raw/LIDO_eclis_failed.csv`.
- The successfully returned data is being divided into `caselaw` and `legislation` citations.
- Selection criteria for the different types of returned caselaw citations are generated with help of the *predecessor_successor_cases* (see [LiDO data format](/datasets/?id=linked-data-overheid-lido)). 
- Finally, the data is stored using the [`Storage` object](/reference/storage). 

### ECHR data

> [!ATTENTION|label:WORK IN PROGRESS]
> The ECHR extraction, transformation, and loading script are still **work in progress**! This is an overview of the current script functionality.

The [ECHR harvester script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/echr/ECHR_metadata_harvester.py) 
extracts all cases from HUDOC.

```bash
$ python3 data_extraction/caselaw/echr/ECHR_metadata_harvester.py local
```
**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Options:**
- `count` (int): number of documents to retrieve

**Output:**
- `data/echr/ECHR_metadata.csv`

**Functionality:**
- Builds the query URL with the endpoint http://hudoc.echr.coe.int/app/query/, filters such as `contentsitename` or `documentcollectionid2`, and arguments such as `start` and `length`.
- Fetches the data from the API and stores it in a `DataFrame` for each page returned.
- Filters only the cases that are in English.
- Finally, the data is stored using the [`Storage` object](/reference/storage). 

### CJEU data

> [!ATTENTION|label:WORK IN PROGRESS]
> The CJEU extraction, transformation, and loading script are still **work in progress**! This is an overview of the current script functionality.

The [cellar extraction script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/cellar/cellar_extraction.py) 
extracts cases from the CELLAR database.

```bash
$ python3 data_extraction/caselaw/cellar/cellar_extraction.py local
```
**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Options:**
- `--amount` (int): number of documents to retrieve
- `--concurrent-docs` (int): default number of documents to retrieve concurrently (200)
- `--starting-date` (str): last modification date to look forward from
- `--fresh` (flag): if present, runs a complete download regardless of existing downloads 

**Output:**
- `data/cellar/`

**Functionality:**
- It queries SPARQL endpoint https://publications.europa.eu/webapi/rdf/sparql for all the ECLIs available in the CELLAR that are related to the CJEU. 
- For each ECLI returned, it queries the API for the metadata of each case, and stores it in a `DataFrame`. 
- The `DataFrame`'s data is exported as a JSON file using the [`Storage` object](/reference/storage).

## Transform

The [data transformation script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_transformation/data_transformer.py) 
transforms the raw data to a uniform format that matches all the datasets, in order to assure all of them follow the same naming conventions and definitions (see more about the [definitions references](/reference/attribute)).

Transform the data available in the `data/raw/` directory. The processed data is stored in the `data/processed/` directory.

```bash
$ python3 data_transformation/data_transformer.py local
```

**Arguments:**
- `storage` (choices: `local`, `aws`): location to take input data from and save output data to (local directory or AWS S3 bucket).

**Input:**  
- `data/raw/RS_cases.csv`
- `data/raw/RS_opinions.csv`
- `data/raw/LI_cases.csv`
    
**Output:**  
- `data/processed/RS_cases_clean.csv`
- `data/processed/RS_opinions_clean.csv`
- `data/processed/LI_cases_clean.csv`

**Functionality:**
- For each input file: reads input file by row
- Maps each row attribute name to global attribute name (see [attribute reference](/reference/attribute))
- Applies adequate transformation function to each row attribute value (see [utils reference](/reference/utils))
- Writes clean row to output file
- Finally, the data is stored using the [`Storage` object](/reference/storage)

## Load

If you would like to load the data into AWS services instead, please first follow our guide on [setting up AWS](/graphql/?id=setup-aws).
Then follow the [Caselaw extraction > Extract](etl/?id=extract) and [Transform](etl/?id=transform) sections with the `location` argument set to **`aws`**.

The [data loader script](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_loading/data_loader.py) 
loads the data into the DynamoDB table and index the OpenSearch domain defined in the `.env` file.

> [!NOTE]
> If you run the script for the first time, the initialization of the OpenSearch services might take some time. 

```bash
python3 data_loading/data_loader.py
```

**Options:**
- `-partial` (choices: `ddb`, `os`): only loads the data to DynamoDB, or only indexes it into OpenSearch, not both.
- `-delete` (choices: `ddb`, `os`): deletes all content from DynamoDB table or OpenSearch index

**Input:**  
- `data/processed/RS_cases_clean.csv`
- `data/processed/RS_opinions_clean.csv`
- `data/processed/LI_cases_clean.csv`
- `data/raw/caselaw_citations.csv`
- `data/raw/legislation_citations.csv`
    
**Output:**
- `data/processed/DDB_eclis_failed.csv`
- `data/processed/OS_eclis_failed.csv`

**Functionality:**

