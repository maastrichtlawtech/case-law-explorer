# Case Law Explorer: ETL

Materials for building a network analysis software platform for analyzing Dutch and European court decisions. This repository builds on the work by Dafne van Kuppevelt of the Netherlands e-Science Centre [NLeSC/case-law-app](https://github.com/NLeSC/case-law-app).

## Quickstart

- **Get started in 5 minutes**: [QUICK_START.md](QUICK_START.md)
- **Caselaw extraction pipeline**: [Caselaw extraction walkthrough](https://maastrichtlawtech.github.io/case-law-explorer/#/etl/)
- **GraphQL API setup**: [GraphQL API walkthrough](https://maastrichtlawtech.github.io/case-law-explorer/#/graphql/)
- **Repository structure**: [Repository Structure](docs/REPOSITORY_STRUCTURE.md)

## System Overview

The **Case Law Explorer** uses Apache Airflow to orchestrate an ETL (Extract, Transform, Load) pipeline that:

1. **Extracts** data from multiple European legal databases
2. **Transforms** data into a consistent, unified format
3. **Loads** data into AWS DynamoDB and S3
4. **Exposes** data through a GraphQL API

### Data Sources

- **[Rechtspraak](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=rechtspraak-archive)** - Dutch courts metadata and decisions
- **[Legal Intelligence](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=legal-intelligence-api)** - Enhanced Dutch legal data
- **[LIDO](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=linked-data-overheid-lido)** - Linked legal citations
- **[ECHR](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=european-court-of-human-rights-echr)** - European Court of Human Rights decisions
- **[CJEU/CELLAR](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=court-of-justice-of-the-european-union-cjeu)** - Court of Justice of the European Union decisions

## Repository Structure

```
airflow/              # Apache Airflow ETL orchestration
├── dags/            # ETL pipeline DAG definitions
├── data/            # Data storage (raw, processed, full_text)
├── logs/            # Execution logs
└── plugins/         # Custom Airflow plugins

docs/                 # Documentation (this is the docs folder)
notebooks/            # Jupyter notebooks for analysis
QUICK_START.md        # 5-minute setup guide
ARCHITECTURE.md       # System architecture diagram
TROUBLESHOOTING.md    # Common issues and solutions
docker-compose.yaml   # Docker services
```

For detailed repository structure, see [Repository Structure](docs/REPOSITORY_STRUCTURE.md).

## Core Technologies

- **Orchestration**: Apache Airflow
- **Containerization**: Docker & Docker Compose
- **Cloud Storage**: AWS DynamoDB, S3, OpenSearch
- **API**: GraphQL (AWS AppSync)
- **Data Processing**: Python 3.8+
- **Analysis**: Jupyter Notebooks

## Documentation

- 📚 **[Full Documentation](https://maastrichtlawtech.github.io/case-law-explorer/)** - Hosted on GitHub Pages
- 🚀 **[Quick Start Guide](QUICK_START.md)** - Get running in 5 minutes
- 🏗️ **[System Architecture](ARCHITECTURE.md)** - Technical design
- 📁 **[Repository Structure](docs/REPOSITORY_STRUCTURE.md)** - Directory organization
- 🔌 **[ETL Pipeline](docs/etl/)** - Data extraction, transformation, loading
- 📊 **[Datasets Reference](docs/datasets/)** - Data source information
- 🔍 **[GraphQL API](docs/graphql/)** - Query interface
- 🛠️ **[Troubleshooting](TROUBLESHOOTING.md)** - Common problems and solutions

## Datasets

See [Datasets](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/). Currently, we gather the case law of the Netherlands and that of two European courts:

- **Published and operable**
    - Rechtspraak (Dutch courts)
    - European Court of Human Rights (ECHR)
    - Court of Justice of the European Union (CJEU)

## Contributors

<!-- readme: contributors,gijsvd -start -->
<table>
<tr>
    <td align="center">
        <a href="https://github.com/BogDAAAMN">
            <img src="https://avatars.githubusercontent.com/u/22895284?v=4" width="100;" alt="BogDAAAMN"/>
            <br />
            <sub><b>Bogdan Covrig</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/maxin-e">
            <img src="https://avatars.githubusercontent.com/u/15159137?v=4" width="100;" alt="maxin-e"/>
            <br />
            <sub><b>maxin-e</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/pedrohserrano">
            <img src="https://avatars.githubusercontent.com/u/12054964?v=4" width="100;" alt="pedrohserrano"/>
            <br />
            <sub><b>Pedro V</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/MarionMeyers">
            <img src="https://avatars.githubusercontent.com/u/23552499?v=4" width="100;" alt="MarionMeyers"/>
            <br />
            <sub><b>MarionMeyers</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/kodymoodley">
            <img src="https://avatars.githubusercontent.com/u/13569029?v=4" width="100;" alt="kodymoodley"/>
            <br />
            <sub><b>Kody Moodley</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/jaspersnel">
            <img src="https://avatars.githubusercontent.com/u/7067980?v=4" width="100;" alt="jaspersnel"/>
            <br />
            <sub><b>Jasper Snel</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/pranavnbapat">
            <img src="https://avatars.githubusercontent.com/u/7271334?v=4" width="100;" alt="pranavnbapat"/>
            <br />
            <sub><b>Pranav Bapat</b></sub>
        </a>
    </td>
</tr>
<tr>
    <td align="center">
        <a href="https://github.com/Cloud956">
            <img src="https://avatars.githubusercontent.com/u/24865274?v=4" width="100;" alt="Cloud956"/>
            <br />
            <sub><b>Piotr Lewandowski</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/brodriguesdemiranda">
            <img src="https://avatars.githubusercontent.com/u/35369949?v=4" width="100;" alt="brodriguesdemiranda"/>
            <br />
            <sub><b>Benjamin Rodrigues de Miranda</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/ChloeCro">
            <img src="https://avatars.githubusercontent.com/u/99276050?v=4" width="100;" alt="ChloeCro"/>
            <br />
            <sub><b>Chloe Crombach</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/running-machin">
            <img src="https://avatars.githubusercontent.com/u/60750154?v=4" width="100;" alt="running-machin"/>
            <br />
            <sub><b>running-machin</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/shashankmc">
            <img src="https://avatars.githubusercontent.com/u/3445114?v=4" width="100;" alt="shashankmc"/>
            <br />
            <sub><b>shashankmc</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/gijsvd">
            <img src="https://avatars.githubusercontent.com/u/31765316?v=4" width="100;" alt="gijsvd"/>
            <br />
            <sub><b>gijsvd</b></sub>
        </a>
    </td>
</tr>
</table>
<!-- readme: contributors,gijsvd -end -->


## License 

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Previously under the [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)), as of 13/02/2022 this work is licensed under a [MIT License](https://opensource.org/licenses/MIT).

```
MIT License

Copyright (c) 2022 Maastricht Law & Tech Lab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
