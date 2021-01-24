#!/bin/bash

# Run rechtspraak extraction scripts
python3 rechtspraak_dump_downloader.py
python3 rechtspraak_dump_unzipper.py
python3 rechtspraak_metadata_dump_parser.py

# Run li extraction scripts
python3 legal_intelligence_extractor.py