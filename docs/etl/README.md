# Data extraction

This walkthrough will teach you how to extract data from the defined sources (see [Datasets](/datasets/)), transform it to be clean and match the global attributes (see [definitions references](/api/attribute)), and store it in the local storage. 

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

Create the environmental variables into the `.env` file, as suggested in [`.env.example` file](https://raw.githubusercontent.com/maastrichtlawtech/case-law-explorer/master/.env.example).  

```.env.example
URL_RS_ARCHIVE=http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip

LI_ENDPOINT=https://api.legalintelligence.com
LI_CLIENT_ID=client@id.here
LI_CLIENT_SECRET=secret-string-here

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
- `LI_` variables are used in the extraction of [Legal Intelligence data](/datasets/?id=legal-intelligence-api). Generate and retrieve the client credentials following the instructions in the [API technical information](https://www.legalintelligence.com/nl/handleidingen/api-technical-information/) of Legal Intelligence.
- `LIDO_` variables are used in the extraction of citations from the [LIDO API](/datasets/?id=linked-data-overheid-lido). One can request a username and password by sending an email to linkeddata@koop.overheid.nl, as per their service documentation.
- `AWS_`, `DDB_`, `OS_`, and `S3_` variables are used to extract and load the data into the AWS services. They are being used and explained in the [GraphQL API Documentation](/graphql/), and not being used in this walkthrough.
- `APPSYNC_ENDPOINT` and `COGNITO_` variables are used in the developer API demos available in the published [notebooks](https://github.com/maastrichtlawtech/case-law-explorer/tree/master/notebooks/api).

## Extract

This scripts will extract data from the defined [datasets](/datasets/) into the local storage.

### Rechtspraak data

Download the latest version of the zipped folder with Rechtspraak data in data `data/OpenDataUitspraken.zip`. 

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader.py local
```

Extract the raw `.xml` files from zipped folder and sub-folders in `data/OpenDataUitspraken.zip`.

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_unzipper.py local
```

Parse the `.xml` files into in `.csv` files into the `data/raw/` directory.  

```bash
$ python3 data_extraction/caselaw/rechtspraak/rechtspraak_metadata_dump_parser.py local
```

### Legal Intelligence data

Extract the Legal Intelligence data available for each case previously extracted from the Rechtspraak archive. The data is stored and merge in the `data/raw/LI_cases.csv` file. 

```bash
$ python3 data_extraction/caselaw/legal_intelligence/legal_intelligence_extractor.py local
```

### LIDO data

Extract the citations provided by the LIDO API for all the available cases previously extracted from the Rechtspraak archive. The data is stored in the `data/raw/caselaw_citations.csv` file (or `legislation`).

```bash
$ python3 data_extraction/citations/rechtspraak_citations_extractor_incremental.py local
```

## Transform

This scripts transform the raw data to an uniform format that matches all the datasets, in order to assure all of them tp follow the same naming conventions and definitions (see more about the [definitions references](/api/attribute)).

Transform the data available in the `data/raw/` directory. The processed data is stored in the `data/processed/` directory.

```bash
$ python3 data_transformation/data_transformer.py local
```

## Load

All the extraction and transformation scripts are passing down to the [`Storage` object](/api/storage) a `storage` arguments. When set to `local`, all the scripts are loading and storing the data **locally** in the `data/` directory. The directory follows the structure of:

<pre>

└── data
    ├── OpenDataUitspraken <i># data parsed from the OpenDataUitspraken.zip archive</i>
    ├── processed <i># data processed as result of the transformation scripts</i>
    └── raw <i># raw data extracted as result of the extractions scripts</i>
    
</pre>

