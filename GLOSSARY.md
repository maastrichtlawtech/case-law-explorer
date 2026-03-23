# Glossary of Technical Terms

A comprehensive glossary of legal, technical, and domain-specific terms used in the Case Law Explorer project.

## Legal Terms

### **ECLI (European Case Law Identifier)**
A uniform identifier system for European case law. Format: `ECLI:CountryCode:Court:Year:Ordinal`

**Example**: `ECLI:NL:HR:2023:1234`
- `NL` = Netherlands
- `HR` = Hoge Raad (Supreme Court)
- `2023` = Year
- `1234` = Sequential number

**Purpose**: Enables unique identification and citation of court decisions across European jurisdictions.

**Resources**: [Official ECLI website](https://e-justice.europa.eu/content_european_case_law_identifier_ecli-175-en.do)

---

### **CELEX (Common European Legal X-change)**
A unique identifier for EU legal documents, including court cases. Format varies by document type.

**Example for Court Case**: `62019CJ0100`
- `6` = Case law
- `2019` = Year
- `CJ` = Court of Justice
- `0100` = Case number

**Purpose**: Identifies all EU legal documents in the EUR-Lex database.

**Resources**: [EUR-Lex CELEX info](https://eur-lex.europa.eu/content/tools/TableOfSectors/types_of_documents_in_eurlex.html)

---

### **BWB (Basis Wetten Bestand)**
The official Dutch abbreviation for the "Basic Laws Database" - the official publication of Dutch laws and regulations.

**Example**: `BWBR0001854` (Dutch Civil Code)
- `BWB` = Basic Laws Database
- `R` = Regulation
- `0001854` = Sequential number

**Purpose**: Unique identification of Dutch legislation.

**Resources**: [wetten.overheid.nl](https://wetten.overheid.nl/)

---

### **Rechtspraak**
Dutch term meaning "case law" or "jurisdiction". Refers to:
1. The Dutch Judiciary (organization)
2. The website rechtspraak.nl hosting Dutch court decisions
3. Dutch case law in general

**Purpose**: Primary source for Dutch court decisions in this project.

**Resources**: [rechtspraak.nl](https://www.rechtspraak.nl/)

---

### **LIDO (Linked Data Overheid)**
"Linked Data Government" - A Dutch government initiative providing linked open data about legislation and case law.

**Services**:
- Citation extraction between cases
- References to legal provisions
- BWB ID mapping
- Legal provision aliases

**Data Format**: RDF/Turtle files with linked data

**Resources**: [linkeddata.overheid.nl](https://linkeddata.overheid.nl/)

---

### **ECHR (European Court of Human Rights)**
International court established by the European Convention on Human Rights.

**Jurisdiction**: Human rights violations in Council of Europe member states

**Database**: HUDOC (Human Rights Documentation)

**Case Identifier**: Uses both ECLI and ItemID systems

**Resources**: [echr.coe.int](https://www.echr.coe.int/)

---

### **CJEU (Court of Justice of the European Union)**
The EU's highest court, interpreting EU law and ensuring uniform application.

**Components**:
- Court of Justice (CJ)
- General Court (GC)

**Database**: CELLAR (Central Repository for Legal Documents)

**Case Identifier**: Uses both ECLI and CELEX

**Resources**: [curia.europa.eu](https://curia.europa.eu/)

---

### **CELLAR**
The Central Repository for Legal Documents of the EU Publications Office.

**Contains**:
- EU legislation
- Court of Justice case law
- Parliamentary documents
- Official Journal

**Access**: SPARQL endpoint for programmatic access

**Resources**: [publications.europa.eu](https://publications.europa.eu/)

---

### **Citation Network**
A graph representation of how court cases reference each other.

**Nodes**: Individual court cases (identified by ECLI)

**Edges**: Citation relationships between cases
- **Outgoing**: Cases cited by this case
- **Incoming**: Cases that cite this case

**Purpose**: Enables network analysis, identifying influential cases, citation patterns, and legal doctrine development.

---

### **Legal Provision**
A specific article, paragraph, or section of a law or regulation that is referenced in a court decision.

**Example**: "Article 1:1 BW" (Article 1:1 of the Dutch Civil Code)

**Components**:
- Law identifier (e.g., BW, Sr)
- Structural elements (Book, Title, Chapter)
- Article number
- Sometimes paragraph and sub-paragraph

---

### **Juriconnect (JCI)**
A standard for unambiguous referencing of legal sources in the Netherlands.

**Format**: `jci1.3:c:BWBR0001854&artikel=1`
- `jci1.3` = Version
- `c` = Type (c=current version)
- `BWBR0001854` = BWB ID
- `artikel=1` = Article 1

**Purpose**: Precise linking to specific parts of legal texts.

---

## Technical Terms

### **ETL (Extract, Transform, Load)**
A data pipeline pattern consisting of three stages:

1. **Extract**: Retrieve data from source systems
2. **Transform**: Clean, normalize, and structure data
3. **Load**: Store data in target system (database, data warehouse)

**In this project**: Extract from rechtspraak.nl/HUDOC/CELLAR → Transform to unified format → Load to DynamoDB/S3

---

### **Apache Airflow**
An open-source platform for orchestrating complex data workflows.

**Key Concepts**:
- **DAG (Directed Acyclic Graph)**: Workflow definition
- **Task**: Individual unit of work
- **Operator**: Template for a task type
- **Scheduler**: Triggers DAGs based on schedule
- **Worker**: Executes tasks

**UI**: Web interface at http://localhost:8080

**Resources**: [airflow.apache.org](https://airflow.apache.org/)

---

### **DAG (Directed Acyclic Graph)**
In Airflow context: A collection of tasks with dependencies, representing a workflow.

**Directed**: Tasks have a defined order (A → B → C)

**Acyclic**: No circular dependencies (prevents infinite loops)

**Example**: Extract → Transform → Load

---

### **Task Group**
In Airflow: A way to organize related tasks together for better visualization and management.

**In this project**: Monthly task groups for parallel processing of different time periods.

---

### **DynamoDB**
AWS's fully managed NoSQL database service.

**Data Model**: Key-value and document database

**Key Features**:
- Automatic scaling
- High availability
- Flexible schema
- Fast performance

**In this project**: Stores case metadata with three tables (ECLI-based, CELEX-based, ItemID-based)

**Resources**: [aws.amazon.com/dynamodb](https://aws.amazon.com/dynamodb/)

---

### **S3 (Simple Storage Service)**
AWS's object storage service.

**Use Cases**: Files, backups, data lakes, static websites

**In this project**: Stores full text of court decisions and graph data (nodes/edges)

**Resources**: [aws.amazon.com/s3](https://aws.amazon.com/s3/)

---

### **GraphQL**
A query language for APIs that allows clients to request exactly the data they need.

**Advantages**:
- Request only needed fields
- Single endpoint
- Strongly typed
- Self-documenting

**In this project**: Optional AppSync API for querying case law data

**Resources**: [graphql.org](https://graphql.org/)

---

### **AppSync**
AWS's managed GraphQL service.

**Features**:
- Automatic schema generation
- Real-time subscriptions
- Built-in authentication
- DynamoDB integration

**In this project**: Provides GraphQL API for querying case data

**Resources**: [aws.amazon.com/appsync](https://aws.amazon.com/appsync/)

---

### **Docker**
Platform for developing, shipping, and running applications in containers.

**Container**: Lightweight, standalone, executable package including code, runtime, libraries, and dependencies.

**In this project**: Airflow and all dependencies run in Docker containers

**Resources**: [docker.com](https://www.docker.com/)

---

### **Docker Compose**
Tool for defining and running multi-container Docker applications.

**In this project**: Orchestrates 6+ services (Airflow webserver, scheduler, worker, PostgreSQL, Redis, etc.)

**Configuration**: `docker-compose.yaml` file

**Resources**: [docs.docker.com/compose](https://docs.docker.com/compose/)

---

### **SPARQL**
Query language for RDF (Resource Description Framework) data.

**Purpose**: Query linked data and semantic web resources

**In this project**: Used to query CELLAR database for CJEU cases

**Example Query**:
```sparql
SELECT ?case ?date WHERE {
  ?case a cdm:judgment .
  ?case cdm:judgmentDate ?date .
}
```

**Resources**: [w3.org/TR/sparql11-query](https://www.w3.org/TR/sparql11-query/)

---

### **RDF (Resource Description Framework)**
Standard model for data interchange on the web.

**Structure**: Triples (Subject-Predicate-Object)

**Example**: 
```
<case123> <hasDate> "2023-01-01"
Subject   Predicate  Object
```

**In this project**: LIDO data is in RDF format

---

### **Turtle (TTL)**
A textual syntax for RDF that is more compact and readable than XML.

**Example**:
```turtle
@prefix ecli: <http://data.europa.eu/eli/ontology#> .

<http://example.org/case/1> 
    ecli:date "2023-01-01" ;
    ecli:court "Supreme Court" .
```

**In this project**: LIDO exports are in Turtle format (`.ttl.gz`)

---

### **Celery**
Distributed task queue for Python.

**Components**:
- **Broker**: Message queue (Redis in this project)
- **Worker**: Executes tasks
- **Result Backend**: Stores task results

**In this project**: Airflow uses Celery to distribute tasks across multiple workers

**Resources**: [docs.celeryproject.org](https://docs.celeryproject.org/)

---

### **PostgreSQL**
Open-source relational database management system.

**Features**:
- ACID compliant
- Advanced SQL features
- Extensible
- Reliable

**In this project**: 
1. Airflow metadata database
2. LIDO legal provisions storage

**Resources**: [postgresql.org](https://www.postgresql.org/)

---

### **Redis**
In-memory data structure store used as database, cache, and message broker.

**In this project**: Celery message broker for Airflow task queue

**Resources**: [redis.io](https://redis.io/)

---

### **Pandas**
Python library for data analysis and manipulation.

**Key Features**:
- DataFrame data structure
- Reading/writing various formats (CSV, JSON, SQL)
- Data cleaning and transformation
- Statistical analysis

**In this project**: Core library for data transformation phase

**Resources**: [pandas.pydata.org](https://pandas.pydata.org/)

---

### **Boto3**
AWS SDK for Python.

**Purpose**: Interact with AWS services programmatically

**In this project**: Used to:
- Upload data to S3
- Write to DynamoDB
- Query AWS resources

**Resources**: [boto3.amazonaws.com](https://boto3.amazonaws.com/)

---

## Data Pipeline Terms

### **Extraction**
First phase of ETL: Retrieving data from source systems.

**In this project**:
- Rechtspraak: Download XML dumps, call metadata API
- ECHR: Query HUDOC API
- CJEU: Query CELLAR SPARQL endpoint
- Citations: Query LIDO API

**Output**: Raw CSV/JSON files in `data/raw/{date}/`

---

### **Transformation**
Second phase of ETL: Cleaning and normalizing data.

**Operations in this project**:
1. Column name normalization
2. Data type conversions
3. XML/HTML parsing
4. ECLI validation
5. Citation structuring
6. Duplicate removal

**Output**: Clean CSV files in `data/processed/{date}/`

---

### **Loading**
Third phase of ETL: Storing data in target systems.

**In this project**:
- Metadata → DynamoDB tables
- Full text → S3 buckets
- Graph data → S3 buckets
- Legal provisions → PostgreSQL

---

### **Incremental Extraction**
Extracting only new or changed data since the last extraction.

**Method**: Using date ranges (start_date, end_date parameters)

**Benefits**:
- Faster processing
- Lower resource usage
- Reduced API calls

---

### **Parallel Processing**
Executing multiple tasks simultaneously.

**In this project**: Monthly task groups process different months in parallel

**Benefits**:
- Faster overall processing
- Better resource utilization
- Independent month processing

---

### **Idempotency**
Property where repeated operations produce the same result.

**Example**: Re-running extraction for a month doesn't create duplicates

**Implementation**: Check if data exists before extraction

---

## Project-Specific Terms

### **Month Directory**
Organization pattern where extracted data is stored in directories by month.

**Format**: `data/raw/YYYY-MM-DD/`

**Example**: `data/raw/2023-01-01/`

**Purpose**: 
- Parallel processing
- Easy reprocessing of specific periods
- Clear data organization

---

### **Metadata Extraction**
Process of extracting structured information about a case (not the full text).

**Includes**:
- Case identifiers (ECLI, CELEX)
- Court name
- Decision date
- Procedure type
- Subject matter
- Citations

---

### **Full Text Extraction**
Process of extracting the complete text of court decisions.

**Storage**: JSON format in S3

**Structure**:
```json
{
  "ecli": "ECLI:NL:HR:2023:1234",
  "full_text": "Court decision text...",
  "sections": {...}
}
```

---

### **Citation Extraction**
Process of identifying and structuring references between cases and to legal provisions.

**Sources**:
- LIDO API (primary)
- Text parsing (secondary)

**Output**:
- Incoming citations (cases citing this case)
- Outgoing citations (cases cited by this case)
- Legal provisions cited

---

### **Graph Data**
Representation of cases and citations as network nodes and edges.

**Nodes File** (`cellar_nodes.txt`):
```
ECLI:NL:HR:2023:1234|Supreme Court|2023-01-01
```

**Edges File** (`cellar_edges.txt`):
```
ECLI:NL:HR:2023:1234|ECLI:NL:HR:2022:5678
```

**Purpose**: Network analysis and visualization

---

## Acronyms Quick Reference

| Acronym | Full Name                              | Category   |
|---------|----------------------------------------|------------|
| AWS     | Amazon Web Services                    | Technology |
| BW      | Burgerlijk Wetboek (Civil Code)        | Legal      |
| BWB     | Basis Wetten Bestand                   | Legal      |
| CELEX   | Common European Legal X-change         | Legal      |
| CJEU    | Court of Justice of the European Union | Legal      |
| DAG     | Directed Acyclic Graph                 | Technology |
| DDB     | DynamoDB                               | Technology |
| ECHR    | European Court of Human Rights         | Legal      |
| ECLI    | European Case Law Identifier           | Legal      |
| ETL     | Extract, Transform, Load               | Technology |
| EU      | European Union                         | Legal      |
| JCI     | Juriconnect                            | Legal      |
| LIDO    | Linked Data Overheid                   | Legal      |
| RDF     | Resource Description Framework         | Technology |
| S3      | Simple Storage Service                 | Technology |
| SPARQL  | SPARQL Protocol and RDF Query Language | Technology |
| SQL     | Structured Query Language              | Technology |
| TTL     | Turtle (file format)                   | Technology |
| UI      | User Interface                         | Technology |
| URL     | Uniform Resource Locator               | Technology |

---

## Need More Information?

- **General Documentation**: See [README.md](README.md)
- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Troubleshooting**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **ETL Guide**: See [docs/etl/README.md](docs/etl/README.md)
- **Datasets**: See [docs/datasets/README.md](docs/datasets/README.md)

---

*Last Updated: October 2025*

