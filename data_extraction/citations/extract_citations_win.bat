Rem create a new python virtual environment and call it "venv"
call python -m venv venv
Rem activate the newly created python virtual environment
call venv/Scripts/activate
Rem install the required python libraries for the citations extractor
call pip install -r requirements.txt
Rem Run the citations extractor on an input file.
Rem "lido-username","lido-password":username and password for the LIDO API. "path/to/inputfile.csv"
Rem is the path to a CSV file that contains a list of ECLI codes, one on each line, for cases from
Rem rechtspraak.nl
call python rechtspraak_citations_extractor.py lido-username lido-password m "path/to/inputfile.csv"
