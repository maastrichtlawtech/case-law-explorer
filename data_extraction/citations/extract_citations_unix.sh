# create a new python virtual environment and call it "venv"
. python -m venv venv
# activate the newly created python virtual environment
. venv/Scripts/activate
# install the required python libraries for the citations extractor
. pip install -r requirements.txt
# Run the citations extractor on an input file.
# "lido-username","lido-password" : username and password for the LIDO API. "path/to/inputfile.csv"
# is the path to a CSV file that contains a list of ECLI codes, one on each line, for cases from
# rechtspraak.nl
. python rechtspraak_citations_extractor.py lido-username lido-password m "path/to/inputfile.csv"
