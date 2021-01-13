# Data extraction
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Turpis egestas pretium aenean pharetra. Orci eu lobortis elementum nibh tellus molestie. Vulputate dignissim suspendisse in est. Vel pharetra vel turpis nunc.

Paths to store data as well as field names and mappings can be defined in `definitions.py`

## Extract
1. Rechtspraak data (contains all decisions and opinions of Dutch case law)
    - Go to: `data_extraction/Rechtspraak`
    - Run `rechtspraak_dump_downloader.py`: Creates zipped folder with Rechtspraak data in `data`. (~25min)
        - output: <path_to_output>/<Rechtspraak_name>.zip file
    - Run `rechtspraak_dump_unzipper.py`: Extracts xml files from zipped folder and subfolders. (~10min)
        - output: <path_to_output>/<Rechtspraak_name> folder
    - Run `rechtspraak_metadata_dump_parser.py`: Parses xml files and stores extracted data in csvs (separated for decisions and opinions, ~1h).
        - output: <path_to_output>/<RS_decisions_name>.csv, <path_to_output>/<RS_opinions_name>.csv
2. Legal Intelligence data (contains supplementary meta data to Rechtspraak data)
    - go to: `data_extraction`
    - Run `legal_intelligence_extractor.py`: Extracts legal intelligence data of most recent publication of each Rechtspraak decision available and stores them in csv. (~4-5h)
        - input: LI user credentials (see `.env.example`)
        - output: <path_to_output>/<LI_name>.csv
3. LIDO data (contains case citations and legislation citations to Rechtspraak data)
    - go to: `data_extraction/citations`
    - Run `rechtspraak_citations_extractor.py`

## Transform
Transform raw data to uniform format

## Load
Load data