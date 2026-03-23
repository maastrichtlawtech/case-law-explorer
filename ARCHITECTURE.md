# Case Law Explorer - System Architecture

## Overview

The Case Law Explorer is an ETL (Extract, Transform, Load) pipeline system that collects, processes, and stores legal case law from multiple European sources. The system uses Apache Airflow for orchestration and AWS services for storage and querying.

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
│  │  - Batch upload to DynamoDB                                          │   │
│  │  - Upload full text to S3                                            │   │
│  │  - Upload graph data (nodes & edges)                                 │   │
│  │  - Error tracking and retry logic                                    │   │
│  └────────────────────────────┬─────────────────────────────────────────┘   │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER (AWS Services)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐           │
│  │   DynamoDB       │  │   Amazon S3      │  │  PostgreSQL      │           │
│  │                  │  │                  │  │  (for LIDO)      │           │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │                  │           │
│  │  │ RS Cases   │  │  │  │ Full Text  │  │  │  ┌────────────┐  │           │
│  │  │ (by ECLI)  │  │  │  │ Documents  │  │  │  │ Legal Case │  │           │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │           │
│  │                  │  │                  │  │  ┌────────────┐  │           │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  │Law Element │  │           │
│  │  │CELLAR Cases│  │  │  │Graph Nodes │  │  │  └────────────┘  │           │
│  │  │(by CELEX)  │  │  │  │  & Edges   │  │  │  ┌────────────┐  │           │
│  │  └────────────┘  │  │  └────────────┘  │  │  │ Case Law   │  │           │
│  │                  │  │                  │  │  └────────────┘  │           │
│  │  ┌────────────┐  │  │                  │  │  ┌────────────┐  │           │
│  │  │ ECHR Cases │  │  │                  │  │  │ Law Alias  │  │           │
│  │  │ (by ItemID)│  │  │                  │  │  └────────────┘  │           │
│  │  └────────────┘  │  │                  │  │                  │           │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘           │
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
Cleaned Data → AWS Services
```
- Metadata → DynamoDB (3 tables: ECLI-based, CELEX-based, ItemID-based)
- Full text → S3 buckets (JSON format)
- Graph data → S3 (nodes and edges for network analysis)
- Legal provisions → PostgreSQL (for LIDO data)

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
- Loads data to AWS services
- Includes error handling and retry logic

#### Utility DAGs
- **`update_citation_details`**: Updates citation information for existing cases
- **`citation_update`**: Batch updates for citation data
- **`lido`**: Processes LIDO export for legal provision linking

### Data Storage Schema

#### DynamoDB Tables

**Table 1: Rechtspraak Cases (Key: ECLI)**
```
Primary Key: ecli (String)
Attributes:
  - date (String)
  - court (String)
  - procedure (List)
  - domains (List)
  - citations_incoming (Set)
  - citations_outgoing (Set)
  - legal_provisions_url (String)
  - full_text_url (String)
  - ...
```

**Table 2: CELLAR Cases (Key: CELEX)**
```
Primary Key: celex (String)
Attributes:
  - ecli (String)
  - year (Number)
  - case_type (String)
  - court (String)
  - full_text_url (String)
  - ...
```

**Table 3: ECHR Cases (Key: ItemID)**
```
Primary Key: item_id (String)
Attributes:
  - ecli (String)
  - case_name (String)
  - judgment_date (String)
  - importance_level (Number)
  - articles_violated (List)
  - full_text_url (String)
  - ...
```

#### S3 Bucket Structure
```
bucket-name/
├── full-text/
│   ├── rechtspraak/
│   │   └── {ecli}.json
│   ├── echr/
│   │   └── {item_id}.json
│   └── cellar/
│       └── {celex}.json
└── graphs/
    ├── cellar_nodes.txt
    ├── cellar_edges.txt
    ├── echr_nodes.txt
    └── echr_edges.txt
```

## Technology Stack

### Core Technologies
- **Python 3.11**: Main programming language
- **Apache Airflow 2.10.5**: Workflow orchestration
- **Docker**: Containerization
- **PostgreSQL 13**: Metadata database (Airflow & LIDO)
- **Redis 7.2**: Celery message broker

### Python Libraries
- **pandas**: Data manipulation
- **boto3**: AWS SDK
- **rechtspraak-extractor**: Dutch case law extraction
- **echr-extractor**: ECHR case extraction
- **cellar-extractor**: CJEU case extraction
- **rechtspraak-citations-extractor**: Citation extraction
- **pyoxigraph**: RDF/Turtle file processing (LIDO)

### AWS Services
- **DynamoDB**: NoSQL database for case metadata
- **S3**: Object storage for full text and graphs
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
    ┌────▼────────┐                         ┌────▼────────┐
    │ Local Data  │                         │ AWS Services│
    │  Volumes    │                         │             │
    │  - dags/    │                         │ - DynamoDB  │
    │  - logs/    │                         │ - S3        │
    │  - data/    │                         │ - AppSync   │
    └─────────────┘                         └─────────────┘
```

## Security Considerations

### Current Implementation
- Environment variables for sensitive credentials
- `.env` file excluded from version control
- AWS IAM for service authentication

### Recommended Improvements
1. Implement proper SSL certificate validation
2. Use AWS Secrets Manager for credential storage
3. Enable encryption at rest for DynamoDB and S3
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
3. **Database Scaling**: Use DynamoDB auto-scaling
4. **Storage Scaling**: S3 scales automatically
5. **Processing Optimization**: Increase parallelization level

## Monitoring and Observability

### Current Monitoring
- Airflow UI for DAG execution status
- Task logs in Airflow
- File-based error tracking (CSV)

### Recommended Additions
1. Prometheus for metrics collection
2. Grafana for visualization
3. CloudWatch for AWS service monitoring
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


