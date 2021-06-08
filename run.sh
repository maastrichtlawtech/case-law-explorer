# Load env variables if exists
if [ -f .env ]; then
    # Load .env file
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')

    # Check of SAMPLE_TEST
    echo "Env variables have been loaded."
    echo "SAMPLE_TEST="$SAMPLE_TEST"\n"
fi

# Run extraction
echo "\033[1m""STARTING EXTRACTION""\033[0m"

cp -r definitions data_extraction/caselaw/rechtspraak/definitions
cp -r definitions data_extraction/caselaw/legal_intelligence/definitions

sh data_extraction/caselaw/extract.sh

rm -rf  data_extraction/caselaw/rechtspraak/definitions
rm -rf  data_extraction/caselaw/legal_intelligence/definitions
