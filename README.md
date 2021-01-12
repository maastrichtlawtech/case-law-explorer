[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)

# Case Law Explorer
Materials for building a network analysis software platform for analyzing Dutch and European court decisions. This repository builds on the work by Dafne van Kuppevelt of the Netherlands e-Science Centre [NLeSC/case-law-app](https://github.com/NLeSC/case-law-app).

This work is licensed under a [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) 

[![License Image: CC BY-NC 4.0](https://licensebuttons.net/l/by-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)

## ETL pipeline

#### 1. Extract raw data and meta data:

1. Rechtspraak data (contains all decisions and opinions of Dutch case law)
    - Go to: `data_extraction/Rechtspraak`
    - Run `rechtspraak_dump_downloader.py`: Creates zipped folder with Rechtspraak data in `data`. (~25min)
    - Run `rechtspraak_dump_unzipper.py`: Extracts xml files from zipped folder and subfolders. (~10min)
    - Run `rechtspraak_metadata_dump_parser.py`: Parses xml files and stores extracted data in csvs (separated for decisions and opinions, ~1h).
2. Legal Intelligence data (contains supplementary meta data to Rechtspraak data)
    - go to: `data_extraction`
    - Run `legal_intelligence_extractor.py`: Extracts legal intelligence data of most recent publication of each Rechtspraak decision available and stores them in csv. (~4-5h)
3. LIDO data (contains case citations and legislation citations to Rechtspraak data)
    - go to: `data_extraction/citations`
    - Run `rechtspraak_citations_extractor.py`
    
#### 2. Transform raw data to uniform format

