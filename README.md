[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)

# Case Law Explorer
Materials for building a network analysis software platform for analyzing Dutch and European court decisions. This repository builds on the work by Dafne van Kuppevelt of the Netherlands e-Science Centre [NLeSC/case-law-app](https://github.com/NLeSC/case-law-app).

This work is licensed under a [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) 

[![License Image: CC BY-NC 4.0](https://licensebuttons.net/l/by-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)

## ETL pipeline

#### 1. Download Rechtspraak data:

in `data_extraction` run `rechtspraak_dump_downloader.py`

- creates zipped folder in `data` with Rechtspraak data

#### 2. Parse meta data:
in `data_extraction/metadata` run `rechtspraak_metadata_dump_parser.py`

- unzips Rechtspraak data
- parses xml files and stores extracted data in csvs.
