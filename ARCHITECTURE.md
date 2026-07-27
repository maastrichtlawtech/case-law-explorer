# Case Law Explorer - System Architecture

## Overview

The Case Law Explorer is an ETL (Extract, Transform, Load) pipeline system that collects, processes, and stores legal case law from multiple European sources. The system uses Apache Airflow for orchestration and Postgres for storage and querying.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │ Rechtspraak  │    │     ECHR     │    │  CJEU/CELLAR │                   │
│  │  (Dutch Law) │    │  (Human Rts) │    │   (EU Law)   │                   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                    │                          │
└─────────┼───────────────────┼────────────────────┼──────────────────────────┘
          │                   │                    │
          │                   │                    │
┌─────────▼───────────────────▼────────────────────▼──────────────────────────┐
│                    EXTRACTION LAYER (Python Libraries)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐     │
│  │ rechtspraak-       │  │ echr-extractor     │  │ cellar-extractor   │     │
│  │ extractor          │  │ (HUDOC API)        │  │ (SPARQL Endpoint)  │     │
│  └─────────┬──────────┘  └─────────┬──────────┘  └──────────┬─────────┘     │
│            │                       │                        │               │
│  ┌─────────▼───────────────────────▼────────────────────────▼──────────┐    │
│  │     rechtspraak-citations-extractor (LIDO API)                      │    │
│  │     - Extracts citations between cases                              │    │
│  │     - Extracts references to legal provisions                       │    │
│  └─────────────────────────────────┬───────────────────────────────────┘    │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER (Apache Airflow)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                         Airflow DAGs                               │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │     │
│  │  │rechtspraak   │  │  echr_etl    │  │ cellar_etl   │              │     │
│  │  │    _etl      │  │              │  │              │              │     │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │     │
│  │         │                 │                 │                      │     │
│  │         └─────────────────┼─────────────────┘                      │     │
│  │                           │                                        │     │
│  │  ┌────────────────────────▼────────────────────────┐               │     │
│  │  │    Monthly Task Groups (Parallel Processing)    │               │     │
│  │  │  - 2023-01  - 2023-02  - 2023-03  ...           │               │     │
│  │  └────────────────────────┬────────────────────────┘               │     │
│  └───────────────────────────┼────────────────────────────────────────┘     │
│                              │                                              │
│  ┌───────────────────────────▼──────────────────────────────────────┐       │
│  │              Additional DAGs                                     │       │
│  │  - update_citation_details (updates existing records)            │       │
│  │  - citation_update (batch updates)                               │       │
│  │  - lido (LIDO extraction for legal provisions)                   │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TRANSFORMATION LAYER (Data Processing)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    data_transformer.py                               │   │
│  │  - Normalize column names across sources                             │   │
│  │  - Clean and format data                                             │   │
│  │  - Apply source-specific transformations                             │   │
│  │  - Validate ECLI identifiers                                         │   │
│  └────────────────────────────┬─────────────────────────────────────────┘   │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LOADING LAYER (Data Persistence)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        data_loader.py                                │   │
│  │  - Upsert case metadata + full text into Postgres (cle_v2)           │   │
│  │  - Upsert citation graph edges into Postgres (cle_v2)                │   │
│  │  - Error tracking and retry logic                                    │   │
│  └────────────────────────────┬─────────────────────────────────────────┘   │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER (Postgres)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Single Postgres instance, two schemas (issue #42 -- see db/README.md):    │
│                                                                             │
│  ┌────────────────────────────────────┐  ┌──────────────────┐              │
│  │  cle_v2 (this ETL's target)        │  │  public (pg_lido)│              │
│  │  ┌────────────┐  ┌────────────┐    │  │  ┌────────────┐  │              │
│  │  │ cases      │  │ case_text  │    │  │  │ legal_case │  │              │
│  │  │ rs_document│  │ (fulltext, │    │  │  └────────────┘  │              │
│  │  │ cjeu_...   │  │  summary)  │    │  │  ┌────────────┐  │              │
│  │  │ echr_...   │  └────────────┘    │  │  │law_element │  │              │
│  │  └────────────┘  ┌────────────┐    │  │  └────────────┘  │              │
│  │  ┌────────────┐  │case_segment│    │  │  ┌────────────┐  │              │
│  │  │case_citation│ │case_summary│    │  │  │ case_law   │  │              │
│  │  └────────────┘  │_version    │    │  │  └────────────┘  │              │
│  │                  └────────────┘    │  │                  │              │
│  └────────────────────────────────────┘  └──────────────────┘              │
│                                                                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      API LAYER (Optional - GraphQL)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      AWS AppSync (GraphQL API)                       │   │
│  │  - Query case law by various criteria                                │   │
│  │  - Search full text                                                  │   │
│  │  - Navigate citation networks                                        │   │
│  │  - Export data for analysis                                          │   │
│  └────────────────────────────┬─────────────────────────────────────────┘   │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATIONS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Case Law Explorer UI                              │   │
│  │  - Web-based interface for exploring case law                        │   │
│  │  - Network visualization of citations                                │   │
│  │  - Advanced search and filtering                                     │   │
│  │  Repository: maastrichtlawtech/case-explorer-ui                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Extraction Phase
```
Source → Extractor Library → Raw CSV/JSON Files
```
- **Rechtspraak**: Metadata from rechtspraak.nl XML dumps
- **ECHR**: Cases from HUDOC API (JSON responses)
- **CJEU**: Cases from CELLAR SPARQL endpoint
- **Citations**: LIDO API enriches data with citation information

**Output Location**: `airflow/data/raw/{date}/`

### 2. Transformation Phase
```
Raw Data → Normalization → Cleaned Data
```
- Column name mapping to unified schema
- Data type conversions
- XML/HTML parsing and cleaning
- ECLI validation
- Citation extraction and structuring

**Output Location**: `airflow/data/processed/{date}/`

### 3. Loading Phase
```
Cleaned Data → Postgres (cle_v2)
```
- Metadata → `cases` + per-source detail tables (`rs_document`, `cjeu_document`, `echr_document`)
- Full text → `case_text.fulltext`
- Graph data → `case_citation` (resolved and unresolved edges)
- Legal provisions → PostgreSQL (`public` schema, for LIDO data, unchanged)

### 4. Enrichment Phase (new, issue #42)
```
case_text.fulltext → case_segmentation DAG → case_segment
case_segment → case_summarization DAG → case_summary_version + case_text.summary
```
- Both DAGs call an external service, `legal-summarizer-service`, over HTTP
  (`/segment`, `/summarize`) -- see `airflow/dags/segmentation/` and
  `airflow/dags/summarization/`.

## Component Details

### Airflow DAGs

#### Main ETL DAGs
- **`rechtspraak_etl`**: Processes Dutch case law
- **`echr_etl`**: Processes European Court of Human Rights cases
- **`cellar_etl`**: Processes Court of Justice of the European Union cases

Each DAG:
- Creates monthly task groups for parallel processing
- Extracts data for specific date ranges
- Transforms data to unified format
- Loads data to Postgres (`cle_v2`)
- Includes error handling and retry logic

#### Utility DAGs
- **`update_citation_details`**: Updates citation information for existing cases
- **`citation_update`**: Batch updates for citation data
- **`lido`**: Processes LIDO export for legal provision linking
- **`case_segmentation`**: Segments case full text via `legal-summarizer-service`, writes `case_segment`
- **`case_summarization`**: Summarizes segmented cases, writes `case_summary_version` + `case_text.summary` (dataset-triggered off `case_segmentation`)

### Data Storage Schema

Full DDL lives in `db/schema.sql` (see `db/README.md` for the schema layout). The `cases` table is the hub, keyed on whichever natural identifier is present:

**`cases`** (Key: `ecli` / `celex_id` / `item_id`, whichever applies)
```
id (bigint, generated)
ecli, celex_id, item_id (each unique, nullable)
title, date_decision, court_id, sources (text[])
```

Per-source detail tables (`rs_document`, `cjeu_document` + `cjeu_national_document`, `echr_document` + `echr_document_article` + `echr_document_appno`) hang off `cases.id` via a `case_id` foreign key, one row per case per source. `case_text` (full text + summary + tsvector/embedding columns, one row per case/language/source) and `case_citation` (resolved via `target_case_id` or unresolved via `target_ecli_raw`/`target_celex_raw`) complete the metadata + full-text + graph picture that DynamoDB + S3 used to split across three tables and two buckets.

## Technology Stack

### Core Technologies
- **Python 3.11**: Main programming language
- **Apache Airflow 2.10.5**: Workflow orchestration
- **Docker**: Containerization
- **PostgreSQL 13**: Airflow metadata + LIDO (`public` schema)
- **PostgreSQL 16 + pgvector**: `cle_v2` schema -- case metadata, full text, citations, segments, summaries (issue #42)
- **Redis 7.2**: Celery message broker

### Python Libraries
- **pandas**: Data manipulation
- **psycopg2 / apache-airflow-providers-postgres**: `cle_v2` + LIDO Postgres access
- **rechtspraak-extractor**: Dutch case law extraction
- **echr-extractor**: ECHR case extraction
- **cellar-extractor**: CJEU case extraction
- **rechtspraak-citations-extractor**: Citation extraction
- **pyoxigraph**: RDF/Turtle file processing (LIDO)

### External Services
- **legal-summarizer-service**: `/segment` and `/summarize` HTTP endpoints called by the `case_segmentation` / `case_summarization` DAGs
- **AppSync** (optional): GraphQL API
- **Cognito** (optional): Authentication

## Deployment Architecture

### Docker Compose Services
```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Network                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  PostgreSQL  │  │    Redis     │  │   Airflow    │       │
│  │   (Port:     │  │  (Port: 6379)│  │  Webserver   │       │
│  │    5432)     │  │              │  │  (Port: 8080)│       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Airflow    │  │   Airflow    │  │   Airflow    │       │
│  │  Scheduler   │  │   Worker     │  │  Triggerer   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         │                                        │
         │                                        │
    ┌────▼────────┐                         ┌──────▼──────┐
    │ Local Data  │                         │ cle-postgres│
    │  Volumes    │                         │  (pgvector, │
    │  - dags/    │                         │  local dev  │
    │  - logs/    │                         │  target for │
    │  - data/    │                         │  pg_cle)    │
    └─────────────┘                         └─────────────┘
```

## Security Considerations

### Current Implementation
- Environment variables for sensitive credentials
- `.env` file excluded from version control
- Airflow connection (`pg_cle`) for Postgres credentials, not raw env vars

### Recommended Improvements
1. Implement proper SSL certificate validation
2. Use a managed secrets store for the `pg_cle` connection and `legal-summarizer-service` credentials
3. Enable encryption at rest for the `cle_v2` Postgres instance
4. Implement VPC for Airflow deployment
5. Add API rate limiting and authentication

## Scalability Considerations

### Current Capacity
- Parallel monthly task processing
- Celery distributed task execution
- Configurable extraction batch sizes

### Scaling Options
1. **Horizontal Scaling**: Add more Airflow workers
2. **Vertical Scaling**: Increase worker resources
3. **Database Scaling**: Standard Postgres scaling (read replicas, connection pooling) for `cle_v2`
4. **Processing Optimization**: Increase parallelization level

## Monitoring and Observability

### Current Monitoring
- Airflow UI for DAG execution status
- Task logs in Airflow
- File-based error tracking (CSV)

### Recommended Additions
1. Prometheus for metrics collection
2. Grafana for visualization
3. Postgres query/connection monitoring (`pg_stat_statements`, connection pool metrics)
4. Structured logging with ELK stack
5. Alerting for pipeline failures

## Related Repositories

- **ETL Pipeline** (this repo): https://github.com/maastrichtlawtech/case-law-explorer
- **User Interface**: https://github.com/maastrichtlawtech/case-explorer-ui
- **Rechtspraak Extractor**: https://pypi.org/project/rechtspraak-extractor/
- **ECHR Extractor**: https://pypi.org/project/echr-extractor/
- **Cellar Extractor**: https://pypi.org/project/cellar-extractor/

## Further Reading

- [ETL Walkthrough](docs/etl/README.md)
- [GraphQL API Setup](docs/graphql/README.md)
- [Dataset Documentation](docs/datasets/README.md)
- [Deployment Guide](docs/deploy/README.md)


