#!/bin/bash

# Run rechtspraak extraction scripts
python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader.py
python3 data_extraction/caselaw/rechtspraak/rechtspraak_dump_unzipper.py
python3 data_extraction/caselaw/rechtspraak/rechtspraak_metadata_dump_parser.py

# Run li extraction scripts
# python3 data_extraction/caselaw/legal_intelligence/legal_intelligence_extractor.py