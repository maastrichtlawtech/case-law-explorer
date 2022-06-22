import json, csv, re, glob
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings("ignore")


from definitions.storage_handler import CELLAR_DIR, DIR_DATA_PROCESSED

# 'WORK_IS_CREATED_BY_AGENT_(AU)',_'CASE_LAW_COMMENTED_BY_AGENT',_'CASE_LAW_HAS_A_TYPE_OF_PROCEDURE',_'LEGAL_RESOURCE_USES_ORIGINALLY_LANGUAGE',_'CASE_LAW_USES_LANGUAGE_OF_PROCEDURE',_'CASE_LAW_HAS_A_JUDICIAL_PROCEDURE_TYPE',_'WORK_HAS_RESOURCE_TYPE',_'LEGAL_RESOURCE_BASED_ON_TREATY_CONCEPT',_'CASE_LAW_ORIGINATES_IN_COUNTRY_OR_USES_A_ROLE_QUALIFIER',_'CASE_LAW_ORIGINATES_IN_COUNTRY',_'CASE_LAW_DELIVERED_BY_COURT_FORMATION',_'LEGAL_RESOURCE_IS_ABOUT_SUBJECT_MATTER',_'RELATED_JOURNAL_ARTICLE',_'CASE_LAW_DELIVERED_BY_ADVOCATE_GENERAL',_'CASE_LAW_DELIVERED_BY_JUDGE',_'ECLI',_'CASE_LAW_INTERPRETS_LEGAL_RESOURCE',_'NATIONAL_JUDGEMENT',_'DATE_CREATION_LEGACY',_'DATETIME_NEGOTIATION',_'SEQUENCE_OF_VALUES',_'DATE_OF_REQUEST_FOR_AN_OPINION',_'CELEX_IDENTIFIER',_'SECTOR_IDENTIFIER',_'NATURAL_NUMBER_(CELEX)',_'TYPE_OF_LEGAL_RESOURCE',_'YEAR_OF_THE_LEGAL_RESOURCE',_'WORK_CITES_WORK._CI_/_CJ',_'LEGACY_DATE_OF_CREATION_OF_WORK',_'DATE_OF_DOCUMENT',_'IDENTIFIER_OF_DOCUMENT',_'WORK_VERSION',_'LAST_CMR_MODIFICATION_DATE',_'CASE_LAW_HAS_CONCLUSIONS'

X = ['WORK IS CREATED BY AGENT (AU)', 'CASE LAW COMMENTED BY AGENT', 'CASE LAW HAS A TYPE OF PROCEDURE', 'LEGAL RESOURCE USES ORIGINALLY LANGUAGE', 'CASE LAW USES LANGUAGE OF PROCEDURE', 'CASE LAW HAS A JUDICIAL PROCEDURE TYPE', 'WORK HAS RESOURCE TYPE', 'LEGAL RESOURCE BASED ON TREATY CONCEPT', 'CASE LAW ORIGINATES IN COUNTRY OR USES A ROLE QUALIFIER', 'CASE LAW ORIGINATES IN COUNTRY', 'CASE LAW DELIVERED BY COURT FORMATION', 'LEGAL RESOURCE IS ABOUT SUBJECT MATTER', 'RELATED JOURNAL ARTICLE', 'CASE LAW DELIVERED BY ADVOCATE GENERAL', 'CASE LAW DELIVERED BY JUDGE', 'ECLI', 'CASE LAW INTERPRETS LEGAL RESOURCE', 'NATIONAL JUDGEMENT', 'DATE_CREATION_LEGACY', 'DATETIME NEGOTIATION', 'SEQUENCE OF VALUES', 'DATE OF REQUEST FOR AN OPINION', 'CELEX IDENTIFIER', 'SECTOR IDENTIFIER', 'NATURAL NUMBER (CELEX)', 'TYPE OF LEGAL RESOURCE', 'YEAR OF THE LEGAL RESOURCE', 'WORK CITES WORK. CI / CJ', 'LEGACY DATE OF CREATION OF WORK', 'DATE OF DOCUMENT', 'IDENTIFIER OF DOCUMENT', 'WORK VERSION', 'LAST CMR MODIFICATION DATE', 'CASE LAW HAS CONCLUSIONS']
Y = ['LEGAL RESOURCE HAS TYPE OF ACT', 'WORK HAS RESOURCE TYPE', 'CASE LAW ORIGINATES IN COUNTRY', 'LEGAL RESOURCE IS ABOUT SUBJECT MATTER', 'ECLI', 'REFERENCE TO PROVISIONS OF NATIONAL LAW', 'PUBLICATION REFERENCE OF COURT DECISION', 'CELEX IDENTIFIER', 'LOCAL IDENTIFIER', 'SECTOR IDENTIFIER', 'TYPE OF LEGAL RESOURCE', 'YEAR OF THE LEGAL RESOURCE', 'WORK IS CREATED BY AGENT (AU)', 'LEGACY DATE OF CREATION OF WORK', 'DATE OF DOCUMENT', 'IDENTIFIER OF DOCUMENT', 'WORK TITLE', 'CMR CREATION DATE', 'LAST CMR MODIFICATION DATE', 'CASE LAW DELIVERED BY NATIONAL COURT', 'REFERENCE TO A EUROPEAN ACT IN FREE TEXT', 'CASE LAW BASED ON A LEGAL INSTRUMENT', 'PARTIES OF THE CASE LAW']

COLS = set(X + Y)
COLS = sorted(COLS)

def create_csv(filepath, encoding="UTF8", data=None, filename="undefined.csv"):
	if data != "":
		csv_file = open(filepath, 'w', encoding=encoding)
		csv_writer = csv.writer(csv_file)
		csv_writer.writerow(COLS)
		csv_writer.writerows(data)
		csv_file.close()
		print("CSV file " + filename + " created in " + DIR_DATA_PROCESSED)

def read_json(file_path):
	with open(file_path, 'r') as f:
		json_data = json.loads(f.read())
	return json_data

def json_to_csv(json_data):
	final_data = []
	for i in json_data:
		ecli_data = json_data[i]

		data = [''] * len(COLS)

		for v in ecli_data.items():
			title = v[0].upper()

			value = str(v[1])
			# Remove new lines
			value = re.sub(r"\\n", '', str(value))
			# Remove blank spaces appearing more than one time
			value = re.sub(r" +", ' ', str(value))
			# Remove brackets
			value = re.sub(r"\[", "", str(value))
			value = re.sub(r"\]", "", str(value))
			# Remove unwanted quotation marks
			value = re.sub(r"'", "", str(value))
			# value = re.sub("\"", "", str(value))
			# Remove semicolon
			value = re.sub(r";", ",", str(value))
			# value = re.sub(r",", " ", str(value))
			# Remove HTML tags
			value = BeautifulSoup(value, "lxml").text

			for j in [j for j, x in enumerate(COLS) if x == title]:
				data[j] = value
		# data.insert(j-1, value)
		# print(j-1, value)

		final_data.append(data)
	return final_data

if __name__ == '__main__':
	json_data = '';

	json_files = (glob.glob(CELLAR_DIR + "/" + "*.json"))

	for i in json_files:
		json_data = read_json(i)

		if json_data:
			final_data = json_to_csv(json_data)

			if final_data:
				filename = i[i.rindex('/') + 1:].partition('.')[0] + ".csv"
				filepath = DIR_DATA_PROCESSED + "/" + filename

				create_csv(filepath=filepath, encoding="UTF8", data=final_data, filename=filename)
			else:
				print("Error creating CSV file. Data is empty.")
		else:
			print("Error reading json file. Please make sure json file exists and contains data.")