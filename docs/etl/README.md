# Data extraction

This walkthrough will teach you how to extract data from the defined sources (see [Datasets](/datasets/)), 
transform it to be clean and in unified format (see [attribute reference](/api/attribute)), and load it to a DynamoDB database. 

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

Create the environmental variables into the `.env` file, as suggested in [`.env.example` file](https://raw.githubusercontent.com/maastrichtlawtech/case-law-explorer/master/.env.example). The following variables are used in the Caselaw extraction (see explanation below):

```.env.example
URL_RS_ARCHIVE=http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip

LI_ENDPOINT=https://api.legalintelligence.com
LI_CLIENT_ID=user@email.here
LI_CLIENT_SECRET=secret-key-here

LIDO_ENDPOINT=http://linkeddata.overheid.nl/service/get-links
LIDO_USERNAME=lido-username-here
LIDO_PASSWORD=lido-pw-here

AWS_ACCESS_KEY_ID=acceskeyid
AWS_SECRET_ACCESS_KEY=secretaccesskey
AWS_REGION=aws-region-here
AWS_DEFAULT_REGION=aws-region-here

DDB_TABLE_NAME=dynamodb-table-name
S3_BUCKET_NAME=s3-bucket-name
OS_DOMAIN_NAME=elasticsearch-domain-name
OS_INDEX_NAME=elasticsearch-index-name

APPSYNC_ENDPOINT=appsync-endpoint-here
COGNITO_USER_KEY=my-user-key-here
COGNITO_CLIENT_ID=client-secret-here
```

The [`.env.example` file](https://raw.githubusercontent.com/maastrichtlawtech/case-law-explorer/master/.env.example) contains the following variables:

- `URL_RS_ARCHIVE` is used in the extraction of the [Rechtspraak archive](/datasets/?id=rechtspraak-archive).
- `LI_` variables are used in the extraction of [Legal Intelligence data](/datasets/?id=legal-intelligence-api). To generate and retrieve the client secret key, log in to [Legal Intelligence](https://www.legalintelligence.com/), go to *User > Instellingen* and click *Aanmaken* under *Persoonlijke gegevens > Secret Key (LI-API)*. For more information, see the [API technical information](https://www.legalintelligence.com/nl/handleidingen/api-technical-information/) of Legal Intelligence.
- `LIDO_` variables are used in the extraction of citations from the [LIDO API](/datasets/?id=linked-data-overheid-lido). One can request a username and password by sending an email to linkeddata@koop.overheid.nl, as per their service documentation.
- `AWS_`, `DDB_`, `OS_`, and `S3_` variables are used to load the data into the AWS services. They are being used and explained in the [GraphQL API Documentation](/graphql/), and not relevant for this walkthrough.
- `APPSYNC_ENDPOINT` and `COGNITO_` variables are used in the Case Law Explorer developer API demos available in the published [notebooks](https://github.com/maastrichtlawtech/case-law-explorer/tree/master/notebooks/api).

## Extract

> [!NOTE]
> All scripts are using the `location` argument. Pass `local` or `aws` as location to read the input data from and store the output data to. 
 
When set to `local`, the script reads and writes input and output data to a **locally** generated `data/` directory. 
When set to `aws`, the script reads and writes input and output data to an automatically generated bucket on **AWS S3**.
Read more about the [`Storage` object](/api/storage). 

In both storage locations, the data directory follows the structure of:
<pre>
 
└── data
    ├── processed <i># processed data as result of the transformation scripts</i>
    ├── raw <i># extracted data as result of the extractions scripts</i>
    └── Rechtspraak <i># data downloaded from Rechtspraak.nl </i>

</pre>

> [!WARNING]
> In both storage locations, data will be overwritten if the same script is called multiple times!

This walkthrough will extract data from the defined [datasets](/datasets/) into the local storage.

### Rechtspraak data

Download the latest version of the zipped folder with Rechtspraak data from 
[http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip](http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip) to `data/Rechtspraak/OpenDataUitspraken.zip`. 

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader.py local
```

Extract the raw `.xml` files from the zipped folder and sub-folders in `data/Rechtspraak/OpenDataUitspraken.zip` to `data/Rechtspraak/OpenDataUitspraken/`.

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_unzipper.py local
```

Parse the `.xml` files from `data/Rechtspraak/OpenDataUitspraken/` into `.csv` files in the `data/raw/` directory.  

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_metadata_dump_parser.py local
```

**Arguments**:
- ``storage`` (choices: ``local``, ``aws``): location to take input data from and save output data to (local directory or AWS S3 bucket).

### Legal Intelligence data

Extract the Legal Intelligence data available for each case previously extracted from the Rechtspraak archive. The data is stored and merge in the `data/raw/LI_cases.csv` file. 

```bash
$ python3 data_extraction/caselaw/legal_intelligence/legal_intelligence_extractor.py local
```

**Arguments**:
- ``storage`` (choices: ``local``, ``aws``): location to take input data from and save output data to (local directory or AWS S3 bucket).

### LIDO data

Extract the citations provided by the LIDO API for all the available cases previously extracted from the Rechtspraak archive. The data is stored in the `data/raw/caselaw_citations.csv` file (or `legislation`).

```bash
$ python3 data_extraction/citations/rechtspraak_citations_extractor_incremental.py local
```

**Arguments**:
- ``storage`` (choices: ``local``, ``aws``): location to take input data from and save output data to (local directory or AWS S3 bucket).

## Transform

This scripts transform the raw data to an uniform format that matches all the datasets, in order to assure all of them tp follow the same naming conventions and definitions (see more about the [definitions references](/api/attribute)).

Transform the data available in the `data/raw/` directory. The processed data is stored in the `data/processed/` directory.

```bash
$ python3 data_transformation/data_transformer.py local
```

**Arguments**:
- ``storage`` (choices: ``local``, ``aws``): location to take input data from and save output data to (local directory or AWS S3 bucket).

## Load

If you would like to load the data into AWS services instead, please first follow our guide on [setting up AWS](/graphql/?id=setup).
Then follow the [Caselaw extraction > Extract](etl/?id=extract) and [Transform](etl/?id=transform) sections with the `location` argument set to **`aws`**.

Now load the data into the DynamoDB table and index the OpenSearch domain with the fresh data.

> [!NOTE]
> If you run the script for the first time, the initialization of the OpenSearch services might take some time. 

```bash
python3 data_loading/data_loader.py
```

**Options:**
- ``-partial`` (choices: ``ddb``, ``os``): only loads the data to DynamoDB, or only indexes it into OpenSearch, not both.
- ``-delete`` (choices: ``ddb``, ``os``): deletes all content from DynamoDB table or OpenSearch index

**Input:**  
    get_path_processed(CSV_RS_CASES),
    get_path_processed(CSV_RS_OPINIONS),
    get_path_processed(CSV_LI_CASES),
    get_path_raw(CSV_CASE_CITATIONS),
    get_path_raw(CSV_LEGISLATION_CITATIONS)
    
**Output:**  
Data loaded into DynamoDB and/or indexed into Opensearch.

**Functionality:**
- this
- that



