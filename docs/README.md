# Case Law Explorer

Materials for building a network analysis software platform for analyzing Dutch and European court decisions. This repository builds on the work by Dafne van Kuppevelt of the Netherlands e-Science Centre [NLeSC/case-law-app](https://github.com/NLeSC/case-law-app).

## Quickstart

- Setup and run locally the extraction pipeline with the [Caselaw extraction walkthrough](etl/)
- Setup and run a GraphQL API with AWS in the [GraphQL API walkthrough](graphql/)

## Datasets

See [Datasets](/datasets/). Currently, we gather the case law of the Netherlands and that of two European courts, as it follows:

- **Published and operable**
    - [Rechtspraak](datasets/?id=rechtspraak-archive), backed by [Legal Intelligence](datasets/?id=legal-intelligence-api), and citations provided by [LIDO](datasets/?id=linked-data-overheid-lido)
- **Work in progress**
    - [European Court of Human Rights](datasets/?id=european-court-of-human-rights-echr) with WIP scripts available on [GitHub](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/echr/ECHR_metadata_harvester.py) 
    - [Court of Justice of the European Union](datasets/?id=court-of-justice-of-the-european-union-cjeu) with WIP scripts available on [GitHub](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/cellar/cellar_extraction.py)

We plan to extend the data to other international courts.

## License 

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Previously under the [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)), as of 13/02/2022 this work is licensed under a [MIT License](https://opensource.org/licenses/MIT).

[LICENSE](https://raw.githubusercontent.com/maastrichtlawtech/case-law-explorer/master/LICENSE ':include :type=code LICENSE')
