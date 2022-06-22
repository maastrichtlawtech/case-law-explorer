# Case Law Explorer: ETL

Materials for building a network analysis software platform for analyzing Dutch and European court decisions. This repository builds on the work by Dafne van Kuppevelt of the Netherlands e-Science Centre [NLeSC/case-law-app](https://github.com/NLeSC/case-law-app).

## Quickstart

- Setup and run locally the extraction pipeline with the [Caselaw extraction walkthrough](https://maastrichtlawtech.github.io/case-law-explorer/#/etl/)
- Setup and run a GraphQL API with AWS in the [GraphQL API walkthrough](https://maastrichtlawtech.github.io/case-law-explorer/#/graphql/)

## Datasets

See [Datasets](/datasets/). Currently, we gather the case law of the Netherlands and that of two European courts, as it follows:

- **Published and operable**
    - [Rechtspraak](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=rechtspraak-archive), backed by [Legal Intelligence](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=legal-intelligence-api), and citations provided by [LIDO](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=linked-data-overheid-lido)
- **Work in progress**
    - [European Court of Human Rights](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=european-court-of-human-rights-echr) with WIP scripts available on [GitHub](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/echr/ECHR_metadata_harvester.py) 
    - [Court of Justice of the European Union](https://maastrichtlawtech.github.io/case-law-explorer/#/datasets/?id=court-of-justice-of-the-european-union-cjeu) with WIP scripts available on [GitHub](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/cellar/cellar_extraction.py)

We plan to extend the data to other international courts.

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
        <a href="https://github.com/gijsvd">
            <img src="https://avatars.githubusercontent.com/u/31765316?v=4" width="100;" alt="gijsvd"/>
            <br />
            <sub><b>gijsvd</b></sub>
        </a>
    </td></tr>
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
