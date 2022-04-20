# Case Law Explorer: ETL

This documentation covers the data pipeline used to extract, transform and load Dutch and European case law from different data sources into an AWS DynamoDB database, as well as the creation of a GraphQL API to query the data (see repository [maastrichtlawtech/case-law-explorer](https://github.com/maastrichtlawtech/case-law-explorer)).
The data transformation and database schema are designed to serve our [Case Law Explorer app](https://dev.d11iy22xsphp3a.amplifyapp.com/) (see repository [maastrichtlawtech/case-explorer-ui](https://github.com/maastrichtlawtech/case-explorer-ui)).
More information about the app can be found in our [use case example](/graphql/?id=usecase-case-law-explorer-ui).

<p align="center">
  <a href="https://github.com/maastrichtlawtech/case-law-explorer">
    <img width="400" alt="case-explorer-ui repository"src="https://ondemand.bannerbear.com/signedurl/D0nJ4XLedwbENRZa1x/image.jpg?modifications=W3sibmFtZSI6InJlcG8iLCJ0ZXh0IjoibWFhc3RyaWNodGxhd3RlY2ggLyAqY2FzZS1sYXctZXhwbG9yZXIqIn0seyJuYW1lIjoiZGVzYyIsInRleHQiOiJNYXRlcmlhbHMgZm9yIGJ1aWxkaW5nIGEgbmV0d29yayBhbmFseXNpcyBzb2Z0d2FyZSBwbGF0Zm9ybSBmb3IgYW5hbHl6aW5nIER1dGNoIGFuZCBFdXJvcGVhbiBjb3VydCBkZWNpc2lvbnMuIn0seyJuYW1lIjoiYXZhdGFyNSIsImltYWdlX3VybCI6Imh0dHBzOi8vYXZhdGFycy5naXRodWJ1c2VyY29udGVudC5jb20vdS8xMzU2OTAyOT92PTQifSx7Im5hbWUiOiJhdmF0YXI0IiwiaW1hZ2VfdXJsIjoiaHR0cHM6Ly9hdmF0YXJzLmdpdGh1YnVzZXJjb250ZW50LmNvbS91LzIzNTUyNDk5P3Y9NCJ9LHsibmFtZSI6ImF2YXRhcjMiLCJpbWFnZV91cmwiOiJodHRwczovL2F2YXRhcnMuZ2l0aHVidXNlcmNvbnRlbnQuY29tL3UvMTIwNTQ5NjQ_dj00In0seyJuYW1lIjoiYXZhdGFyMiIsImltYWdlX3VybCI6Imh0dHBzOi8vYXZhdGFycy5naXRodWJ1c2VyY29udGVudC5jb20vdS8xNTE1OTEzNz92PTQifSx7Im5hbWUiOiJhdmF0YXIxIiwiaW1hZ2VfdXJsIjoiaHR0cHM6Ly9hdmF0YXJzLmdpdGh1YnVzZXJjb250ZW50LmNvbS91LzIyODk1Mjg0P3Y9NCJ9LHsibmFtZSI6ImNvbnRyaWJ1dG9ycyIsInRleHQiOiIxMiBDb250cmlidXRvcnMifSx7Im5hbWUiOiJzdGFycyIsInRleHQiOiI0In1d&s=4d11348fcdb6618b59835346f9816cf5e36511d9cace30a12e19f408952bec2e" />
  </a>
  <a href="https://github.com/maastrichtlawtech/case-explorer-ui/tree/dev">
    <img width="400" alt="case-explorer-ui repository"src="https://ondemand.bannerbear.com/signedurl/D0nJ4XLedwbENRZa1x/image.jpg?modifications=W3sibmFtZSI6InJlcG8iLCJ0ZXh0IjoibWFhc3RyaWNodGxhd3RlY2ggLyAqY2FzZS1leHBsb3Jlci11aSoifSx7Im5hbWUiOiJkZXNjIiwidGV4dCI6IlVzZXIgaW50ZXJmYWNlIGZvciB0aGUgbmV0d29yayBhbmFseXNpcyBzb2Z0d2FyZSBwbGF0Zm9ybSBmb3IgYW5hbHl6aW5nIER1dGNoIGFuZCBFdXJvcGVhbiBjb3VydCBkZWNpc2lvbnMuIn0seyJuYW1lIjoiYXZhdGFyNSIsImhpZGUiOnRydWV9LHsibmFtZSI6ImF2YXRhcjQiLCJoaWRlIjp0cnVlfSx7Im5hbWUiOiJhdmF0YXIzIiwiaGlkZSI6dHJ1ZX0seyJuYW1lIjoiYXZhdGFyMiIsImhpZGUiOnRydWV9LHsibmFtZSI6ImF2YXRhcjEiLCJpbWFnZV91cmwiOiJodHRwczovL2F2YXRhcnMuZ2l0aHVidXNlcmNvbnRlbnQuY29tL3UvNTI0NTIxNzQ_dj00In0seyJuYW1lIjoiY29udHJpYnV0b3JzIiwidGV4dCI6Im1hYXN0cmljaHRsYXd0ZWNoIn0seyJuYW1lIjoic3RhcnMiLCJ0ZXh0IjoiMSJ9XQ&s=63623cdd33143e92e6c069caa3610262a98c2b9a8aef8f8ca79e77e58aab023c" />
  </a>
</p>

## Quickstart

- Setup and run the ETL pipeline with the [Caselaw extraction walkthrough](etl/)
- Setup and run a GraphQL API with AWS in the [GraphQL API walkthrough](graphql/)

## Datasets

See [Datasets](/datasets/). Currently, we gather the case law of the Netherlands and that of two European courts, as it follows:

- **Published and operable**
    - [Rechtspraak](datasets/?id=rechtspraak-archive), backed by [Legal Intelligence](datasets/?id=legal-intelligence-api), and citations provided by [LiDO](datasets/?id=linked-data-overheid-lido)
- **Work in progress**
    - [European Court of Human Rights](datasets/?id=european-court-of-human-rights-echr) with WIP scripts available on [GitHub](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/echr/ECHR_metadata_harvester.py) 
    - [Court of Justice of the European Union](datasets/?id=court-of-justice-of-the-european-union-cjeu) with WIP scripts available on [GitHub](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/cellar/cellar_extraction.py)

We plan to extend the data to other international courts.

## License 

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Previously under the [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en), as of 13/02/2022 this work is licensed under a [MIT License](https://opensource.org/licenses/MIT).

[LICENSE](https://raw.githubusercontent.com/maastrichtlawtech/case-law-explorer/master/LICENSE ':include :type=code LICENSE')
