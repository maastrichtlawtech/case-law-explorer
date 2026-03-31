# Data Extraction, Transformation, and Loading (ETL)

This walkthrough will teach you how to extract data from defined sources, transform it to a clean and unified format, and optionally load it to an AWS DynamoDB database using Apache Airflow.
For more information about the data sources and the format of the extracted data, see [Datasets](/datasets/).

## Setup with Docker & Airflow (Recommended)

The Case Law Explorer uses **Apache Airflow** to orchestrate the ETL pipeline. This ensures reliable, scheduled, and monitored data processing.

> [!WARNING|label:Pre-requirements]
> - [Docker & Docker Compose](https://www.docker.com/products/docker-desktop) installed
> - [Git](https://git-scm.com/) installed
> - 8GB+ RAM available
> - 10GB+ free disk space

### Quick Start with Docker

Clone the [maastrichtlawtech/case-law-explorer](https://github.com/maastrichtlawtech/case-law-explorer) project.

```bash
$ git clone https://github.com/maastrichtlawtech/case-law-explorer
$ cd case-law-explorer
```

Copy and configure the environment file:

```bash
$ cp .env.example .env
$ nano .env  # or use your favorite editor
```

Start the services:

```bash
$ docker-compose up -d
# Wait 2-3 minutes for services to initialize
$ docker-compose ps  # Verify all services are running
```

Access Airflow at **http://localhost:8080** with credentials:
- **Username**: `airflow`
- **Password**: `airflow`

### Environment Variables

Create the environmental variables in the `.env` file. The following variables are essential:

```.env.example
# Airflow Configuration
AIRFLOW_UID=50000
DATA_PATH=/opt/airflow/data

# AWS Configuration (optional, for cloud deployment)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
AWS_DEFAULT_REGION=

DDB_TABLE_NAME=caselawexplorer-test
DDB_TABLE_NAME_CELEX=caselawexplorer-celex-test
DDB_NAME_ECHR=caselawexplorer-echr-test
S3_BUCKET_NAME=caselawexplorer-load-test
CELLAR_NODES_BUCKET_NAME=cellar-nodes-edges-bucket

# Optional: AWS AppSync for GraphQL
APPSYNC_ENDPOINT=appsync-endpoint-here
COGNITO_USER_KEY=my-user-key-here
COGNITO_CLIENT_ID=client-secret-here

# LIDO API for citations (Rechtspraak only)
LIDO_ENDPOINT=http://linkeddata.overheid.nl/service/get-links
LIDO_USERNAME=lido-username-here
LIDO_PASSWORD=lido-pw-here

# EUR-Lex links for CJEU cases
CELEX_SUBSTITUTE=cIdHere
EURLEX_SUMMARY_LINK_INF=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere&from=EN
EURLEX_SUMMARY_LINK=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere_SUM&from=EN
EURLEX_SUMJURE_LINK=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=URISERV:cIdHere_SUMJURE&from=EN
EURLEX_ALL_DATA=https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:cIdHere
EURLEX_FULL_TEXT=https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:cIdHere&from=EN

# CJEU/CELLAR Web Service
EURLEX_WEBSERVICE_USERNAME=
EURLEX_WEBSERVICE_PASSWORD=
```

### Storage Location Structure

The data directory in `airflow/data/` follows this structure:

```
airflow/data/
├── processed/        # Cleaned and transformed data ready for loading
├── raw/              # Raw extracted data from sources
├── full_text/        # Full text content (Cellar and ECHR cases)
└── eclis/            # ECLI identifier lists
```

For more details, see the [`Storage` object documentation](/reference/storage).

### Setting Airflow Variables

Configure variables in the Airflow UI (Admin → Variables) for runtime configuration:

| Variable | Example | Description |
|----------|---------|-------------|
| `RS_START_DATE` | `"2023-01-01"` | Start date for Rechtspraak extraction |
| `RS_END_DATE` | `"2023-12-31"` | End date for Rechtspraak extraction |
| `RS_AMOUNT_TO_EXTRACT` | `"100"` | Number of Rechtspraak cases to extract |
| `ECHR_START_DATE` | `"2023-01-01"` | Start date for ECHR extraction |
| `ECHR_END_DATE` | `"2023-12-31"` | End date for ECHR extraction |
| `ECHR_AMOUNT_TO_EXTRACT` | `"100"` | Number of ECHR cases to extract |
| `CELLAR_START_DATE` | `"2023-01-01"` | Start date for CELLAR extraction |
| `CELLAR_END_DATE` | `"2023-12-31"` | End date for CELLAR extraction |
| `CELLAR_AMOUNT_TO_EXTRACT` | `"100"` | Number of CELLAR cases to extract |
| `DATA_PATH` | `"/opt/airflow/data"` | Base path for data storage |

## Extract

This section describes the extraction of data from the defined [datasets](/datasets/) using Airflow DAGs.

If you wish to eventually load the processed data into an AWS DynamoDB database, please first follow our guide on [setting up AWS](/graphql/?id=setup-aws).

### Available DAGs

### Rechtspraak data

The [Rechtspraak extractor](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/airflow/dags/rechtspraak/tasks/rechtspraak_extraction.py) 
downloads the metadata of Dutch Court cases available at 
[https://data.rechtspraak.nl/Uitspraken](https://data.rechtspraak.nl/Uitspraken) to `airflow/data/raw/RS_cases.csv`.

The extraction is orchestrated through the **Airflow DAG** `rechtspraak_etl`, which:
- Runs monthly task groups for parallel-safe data processing
- Uses centralized, parameterized extraction logic
- Passes unique output directories for each month to ensure no conflicts
- Chains extraction → transformation → loading in sequence

```bash
# Access the DAG at http://localhost:8080 after starting Docker
# Or trigger manually:
$ airflow dags trigger rechtspraak_etl
```

**Configuration:**
Set these Airflow Variables in the Admin → Variables UI:
- `RS_START_DATE`: Start date for extraction (e.g., "2023-01-01")
- `RS_END_DATE`: End date for extraction (e.g., "2023-12-31")
- `RS_AMOUNT_TO_EXTRACT`: Number of cases to extract per run
- `DATA_PATH`: Base path for data storage (default: `/opt/airflow/data`)

**Output:**
- `airflow/data/raw/RS_cases.csv` - Raw metadata
- `airflow/data/processed/rechtspraak_*.csv` - Processed data ready for loading
---
**Functionality:**
- Uses the [rechtspraak-extractor](https://pypi.org/project/rechtspraak-extractor/) library to download metadata
- Automatically validates and handles citations via the [rechtspraak-citations-extractor](https://pypi.org/project/rechtspraak-citations-extractor/)
- Transformation normalizes column names and formats data
- Loading pushes processed data to AWS DynamoDB (if configured)

### ECHR data

The [ECHR extractor](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/airflow/dags/echr/tasks/echr_extraction.py) 
extracts all cases from HUDOC (European Court of Human Rights database).

The extraction is orchestrated through the **Airflow DAG** `echr_extraction_monthly`, which:
- Runs monthly task groups for parallel-safe data processing
- Uses centralized, parameterized extraction logic via the [echr-extractor](https://pypi.org/project/echr-extractor/) library
- Chains extraction → transformation → loading in sequence

```bash
# Access the DAG at http://localhost:8080 after starting Docker
# Or trigger manually:
$ airflow dags trigger echr_extraction_monthly
```

**Configuration:**
Set these Airflow Variables in the Admin → Variables UI:
- `ECHR_START_DATE`: Start date for extraction (e.g., "2023-01-01")
- `ECHR_END_DATE`: End date for extraction (e.g., "2023-12-31")
- `ECHR_AMOUNT_TO_EXTRACT`: Number of cases to extract per run
- `DATA_PATH`: Base path for data storage (default: `/opt/airflow/data`)

**Output:**
- `airflow/data/raw/ECHR_metadata.csv` - Raw metadata
- `airflow/data/processed/echr_*.csv` - Processed data ready for loading

**Functionality:**
- Builds the query URL with the endpoint http://hudoc.echr.coe.int/app/query/, filters such as `contentsitename` or `documentcollectionid2`, and arguments such as `start` and `length`.
- Fetches the data from the API and stores it in a `DataFrame` for each page returned.
- Extracts full text and stores it separately for efficient retrieval
- Transformation normalizes column names and formats data
- Loading pushes processed data to AWS DynamoDB (if configured)

### CJEU data (Cellar)

The [Cellar extractor](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/airflow/dags/cellar/tasks/cellar_extraction.py) 
extracts cases from the CELLAR database (Court of Justice of the European Union).

The extraction is orchestrated through the **Airflow DAG** `cellar_extraction_monthly`, which:
- Runs monthly task groups for parallel-safe data processing
- Uses centralized, parameterized extraction logic via the [cellar-extractor](https://pypi.org/project/cellar-extractor/) library
- Chains extraction → transformation → loading in sequence
- Generates both case metadata and graph data (nodes & edges)

```bash
# Access the DAG at http://localhost:8080 after starting Docker
# Or trigger manually:
$ airflow dags trigger cellar_extraction_monthly
```

**Configuration:**
Set these Airflow Variables in the Admin → Variables UI:
- `CELLAR_START_DATE`: Start date for extraction (e.g., "2023-01-01")
- `CELLAR_END_DATE`: End date for extraction (e.g., "2023-12-31")
- `CELLAR_AMOUNT_TO_EXTRACT`: Number of cases to extract per run
- `DATA_PATH`: Base path for data storage (default: `/opt/airflow/data`)

**Output:**
- `airflow/data/raw/cellar_csv_data.csv` - Raw metadata
- `airflow/data/full_text/cellar_full_text.json` - Full text data
- `airflow/data/processed/cellar_nodes.txt` - Graph nodes for network analysis
- `airflow/data/processed/cellar_edges.txt` - Graph edges for network analysis
- `airflow/data/processed/cellar_*.csv` - Processed data ready for loading

**Functionality:**
- Queries SPARQL endpoint https://publications.europa.eu/webapi/rdf/sparql for all ECLIs in CELLAR related to CJEU
- For each ECLI, fetches metadata and stores it in structured format
- Extracts full text and stores separately for efficient retrieval
- Generates network graph data (nodes and edges) for citation analysis
- Transformation normalizes column names and formats data
- Loading pushes processed data to AWS DynamoDB and S3 (if configured)
- For more details, see the [cellar-extractor](https://pypi.org/project/cellar-extractor/) library

## Transform

The [data transformation module](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/airflow/dags/shared/data_transformation/)
transforms the raw data from all sources into a uniform format that matches all datasets, ensuring consistent naming conventions and definitions (see more about the [definitions references](/reference/attribute)).

Transform the data available in the `airflow/data/raw/` directory. The processed data is stored in the `airflow/data/processed/` directory.

The transformation is executed within each source's Airflow DAG:

```bash
# Transformations run automatically as part of DAGs:
$ airflow dags trigger rechtspraak_etl
$ airflow dags trigger echr_extraction_monthly
$ airflow dags trigger cellar_extraction_monthly
```

**Input:**  
- `airflow/data/raw/cellar_csv_data.csv`
- `airflow/data/raw/ECHR_metadata.csv`
- `airflow/data/raw/RS_cases.csv`
    
**Output:**  
- `airflow/data/processed/cellar_csv_data_clean.csv`
- `airflow/data/processed/ECHR_metadata_clean.csv`
- `airflow/data/processed/RS_cases_clean.csv`

**Functionality:**
- For each input file: reads input file by row
- Maps each row attribute name to global attribute name (see [attribute reference](/reference/attribute))
- Applies adequate transformation function to each row attribute value (see [utils reference](/reference/utils))
- Writes clean row to output file
- Finally, the data is stored using the [`Storage` object](/reference/storage)

## Load

If you would like to load the data into AWS services instead, please first follow our guide on [setting up AWS](/graphql/?id=setup-aws).

The [data loader module](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/airflow/dags/shared/data_loading/)
loads the transformed data into the DynamoDB table defined in the `.env` file.

The loading is executed automatically as part of each source's Airflow DAG, following transformation:

```bash
# Loading runs automatically as part of DAGs:
$ airflow dags trigger rechtspraak_etl
$ airflow dags trigger echr_extraction_monthly
$ airflow dags trigger cellar_extraction_monthly
```

**Input:**  
- `airflow/data/processed/cellar_csv_data_clean.csv`
- `airflow/data/processed/RS_cases_clean.csv`
- `airflow/data/processed/ECHR_metadata_clean.csv`
- `airflow/data/full_text/cellar_full_text.json`
- `airflow/data/full_text/ECHR_full_text.json`
- `airflow/data/processed/cellar_edges.txt`
- `airflow/data/processed/cellar_nodes.txt`
- `airflow/data/processed/ECHR_edges.txt`
- `airflow/data/processed/ECHR_nodes.txt`
    
**Output:**
- `airflow/data/processed/DDB_eclis_failed.csv` - Failed items for debugging
- Data uploaded to AWS DynamoDB and S3 (if configured)

**Functionality:**
- For each input file: reads processed data by row
- Creates items to put or update in DynamoDB table according to key schema (see [row_processors reference](reference/row-processors))
- Creates items to index or update in OpenSearch index (if enabled) ([row_processors reference](/reference/row-processors/?id=opensearch-service))
- Loads items to DynamoDB table and/or OpenSearch index as defined in `.env` file
- Writes errors and item keys/IDs of failed loading attempts to `airflow/data/processed/DDB_eclis_failed.csv`
- For each full_text file: uploads separate json files containing full-text information for each ECHR/CELLAR case to AWS S3 bucket
- For graph data (nodes and edges): uploads to graph analysis bucket for network visualization