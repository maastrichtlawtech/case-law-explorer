# Repository Structure

This document describes the organization and structure of the Case Law Explorer repository.

## Overview

```
case-law-explorer/
├── airflow/                    # Apache Airflow ETL orchestration
│   ├── dags/                  # Airflow DAG definitions
│   ├── logs/                  # Airflow logs
│   ├── data/                  # Data storage for ETL pipeline
│   ├── plugins/               # Custom Airflow plugins
│   ├── Dockerfile             # Docker image for Airflow
│   └── requirements*.txt       # Python dependencies
├── docs/                      # Documentation (this folder)
├── notebooks/                 # Jupyter notebooks for analysis
├── archive/                   # Legacy/archived code
├── ARCHITECTURE.md            # System architecture diagram
├── QUICK_START.md             # Quick start guide
├── TROUBLESHOOTING.md         # Troubleshooting guide
├── README.md                  # Main repository README
├── docker-compose.yaml        # Docker services orchestration
└── .env.example              # Environment variable template
```

## Key Directories

### `/airflow` - ETL Pipeline Orchestration

The core ETL (Extract, Transform, Load) pipeline is orchestrated through Apache Airflow.

```
airflow/
├── dags/                           # Airflow DAG definitions
│   ├── rechtspraak/               # Rechtspraak (Dutch courts) extraction DAG
│   │   ├── dag.py                # Main DAG definition
│   │   ├── tasks/
│   │   │   ├── rechtspraak_extraction.py
│   │   │   ├── rechtspraak_transformation.py
│   │   │   └── rechtspraak_loading.py
│   │   └── utils/
│   ├── echr/                      # ECHR (European Court of Human Rights) extraction DAG
│   │   ├── dag.py
│   │   ├── tasks/
│   │   │   ├── echr_extraction.py
│   │   │   ├── echr_transformation.py
│   │   │   └── echr_loading.py
│   │   └── utils/
│   ├── cellar/                    # CJEU/CELLAR (Court of Justice) extraction DAG
│   │   ├── dag.py
│   │   ├── tasks/
│   │   │   ├── cellar_extraction.py
│   │   │   ├── cellar_transformation.py
│   │   │   └── cellar_loading.py
│   │   └── utils/
│   ├── lido/                      # LIDO (Linked Data Overheid) extraction
│   │   ├── dag.py
│   │   ├── tasks/
│   │   └── utils/
│   ├── lido_sqlite_monthly/       # Monthly LIDO SQLite database
│   │   ├── dag.py
│   │   └── tasks/
│   ├── maintenance/               # Maintenance tasks
│   │   ├── citation_update/       # Citation metadata updates
│   │   ├── log_cleaner/           # Log cleanup
│   │   └── update_citation_details/
│   ├── shared/                    # Shared utilities and modules
│   │   ├── data_extraction/       # Extraction utilities
│   │   ├── data_transformation/   # Transformation utilities
│   │   ├── data_loading/          # Loading utilities
│   │   ├── definitions/           # Data definitions and schema
│   │   └── helpers/               # Helper functions
│   └── README_ETL_UPGRADE.md     # Documentation on DAG upgrades
├── data/                          # Data storage
│   ├── raw/                       # Raw extracted data
│   ├── processed/                 # Processed/transformed data
│   ├── full_text/                 # Full text content storage
│   └── eclis/                     # ECLI identifier lists
├── logs/                          # Airflow scheduler and DAG logs
│   ├── scheduler/
│   ├── dag_processor_manager/
│   └── dag_id=*/                 # Logs organized by DAG ID
├── plugins/                       # Custom Airflow plugins and operators
├── Dockerfile                     # Docker image definition for Airflow
├── requirements.txt               # Python package dependencies
├── requirements-pinned.txt        # Pinned versions for reproducibility
└── .env                          # Environment configuration (git-ignored)
```

### `/docs` - Documentation

Documentation for the system, organized by topic:

```
docs/
├── README.md              # Documentation main page and overview
├── REPOSITORY_STRUCTURE.md # This file - repository organization
├── _sidebar.md            # Docsify navigation sidebar
├── index.html             # Docsify HTML entry point
├── .nojekyll              # Disables Jekyll processing on GitHub Pages
├── etl/                   # ETL pipeline documentation
│   └── README.md         # Extract, Transform, Load walkthrough
├── graphql/               # GraphQL API documentation
│   └── README.md         # API setup and usage guide
├── datasets/              # Data source documentation
│   └── README.md         # Datasets overview and descriptions
├── setup/                 # Setup and configuration
│   └── README.md         # Adding new data sources
├── deploy/                # Deployment documentation
│   └── README.md         # Production deployment guide
├── reference/             # API reference documentation
│   ├── attribute.md      # Data field definitions
│   ├── storage.md        # Storage class reference
│   └── README.md         # Reference overview
└── icons/                 # Icon assets for documentation
```

### `/notebooks` - Jupyter Notebooks

Analysis and exploration notebooks:

```
notebooks/
├── ECHR_metadata_harvester.ipynb     # ECHR data extraction notebook
├── gql_queries.py                    # GraphQL query helper functions
├── query_API.ipynb                   # API query examples
├── analysis/                         # Analysis notebooks
│   ├── data_metrics.ipynb           # Data quality metrics
│   ├── data_raw_inspection.ipynb    # Raw data inspection
│   └── output/                       # Analysis results
└── api/                              # API testing
    ├── gql_queries.py
    └── query_API.ipynb
```

### `/archive` - Legacy Code

Previously used code and deprecated implementations:

```
archive/
├── docker-compose.yaml    # Legacy Docker setup
├── Dockerfile            # Legacy Docker image
└── requirements.txt      # Legacy dependencies
```

## Data Flow

```
Data Sources (Rechtspraak, ECHR, CELLAR)
           ↓
    Airflow DAGs
           ↓
     ┌─────┴─────┐
     ↓           ↓
  Extract    Transform
     ↓           ↓
  Load ←────────┘
     ↓
┌─────┴─────┐
↓           ↓
DynamoDB   S3/File Storage
↓
GraphQL API Interface
```

## DAG Organization

### Monthly ETL DAGs

The main extraction DAGs organize work in monthly task groups:

- **`rechtspraak_etl`** - Rechtspraak (Dutch courts)
  - Trigger: Manual or scheduled
  - Frequency: Monthly task groups
  - Output: CSV files, citation data

- **`echr_extraction_monthly`** - ECHR (Human Rights Court)
  - Trigger: Manual or scheduled
  - Frequency: Monthly task groups
  - Output: CSV files, full text JSON, graph data

- **`cellar_extraction_monthly`** - CJEU/CELLAR (EU Court of Justice)
  - Trigger: Manual or scheduled
  - Frequency: Monthly task groups
  - Output: CSV files, full text JSON, graph nodes & edges

### Maintenance DAGs

- **`update_citation_details`** - Updates citation metadata
- **`citation_update`** - Batch citation updates
- **`lido`** - LIDO (Legal Intelligence) extraction
- **`lido_sqlite_monthly`** - Monthly LIDO SQLite database
- **`log_cleaner`** - Periodic log cleanup

## Shared Components

The `/airflow/dags/shared/` directory contains reusable modules:

### Data Extraction (`data_extraction/`)
- Source-specific extraction logic
- API interactions
- Data validation

### Data Transformation (`data_transformation/`)
- Data cleaning and normalization
- Column mapping across sources
- Format standardization (CSV, JSON, etc.)

### Data Loading (`data_loading/`)
- AWS DynamoDB integration
- S3 uploads
- OpenSearch indexing
- Error handling and retry logic

### Definitions (`definitions/`)
- Schema definitions
- Storage path configurations
- Data type mappings

### Helpers (`helpers/`)
- Utility functions
- Common operations
- Logging helpers

## Environment Configuration

The `.env` file (not committed to git) contains:

- **Airflow settings**: `AIRFLOW_UID`, `DATA_PATH`
- **AWS credentials**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, etc.
- **Database configuration**: `DDB_TABLE_NAME`, `S3_BUCKET_NAME`, etc.
- **API credentials**: `LIDO_USERNAME`, `EURLEX_WEBSERVICE_USERNAME`, etc.
- **Office Endpoints**: LIDO endpoint, EUR-Lex links, etc.

See `.env.example` for all available variables.

## Documentation Navigation

- **Getting Started**: [QUICK_START.md](/QUICK_START.md)
- **System Architecture**: [ARCHITECTURE.md](/ARCHITECTURE.md)
- **ETL Pipeline Guide**: [docs/etl/](/docs/etl/)
- **Datasets Reference**: [docs/datasets/](/docs/datasets/)
- **GraphQL API**: [docs/graphql/](/docs/graphql/)
- **Troubleshooting**: [TROUBLESHOOTING.md](/TROUBLESHOOTING.md)
- **Data Definitions**: [docs/reference/attribute.md](/docs/reference/attribute.md)
- **Storage Reference**: [docs/reference/storage.md](/docs/reference/storage.md)

## Development Workflow

1. **Extract**: Raw data pulled from sources by DAG tasks
2. **Transform**: Data normalized and validated
3. **Load**: Data stored in DynamoDB and S3
4. **Query**: Data accessed via GraphQL API
5. **Analyze**: Analysis notebooks for insights

## Key Technologies

- **Orchestration**: Apache Airflow
- **Containerization**: Docker & Docker Compose
- **Data Storage**: AWS DynamoDB, S3
- **Extraction Libraries**: 
  - `rechtspraak-extractor`
  - `echr-extractor`
  - `cellar-extractor`
  - `rechtspraak-citations-extractor`
- **Query Interface**: GraphQL (AWS AppSync)
- **Analysis**: Jupyter Notebooks
- **Version Control**: Git/GitHub

## Contributing

When adding new features or data sources:

1. Follow the existing DAG structure in `airflow/dags/`
2. Use the shared modules in `shared/` for extraction, transformation, loading
3. Add documentation in the appropriate `docs/` subdirectory
4. Update this file if changing repository structure
5. Ensure all new code is tested and validated
