"""
Script that defines the terminology to be used throughout all data processing steps.
The original terms used in the raw data of "Rechtspraak" and "Legal intelligence" are mapped to each other
and replaced by a global label.
Original Rechtspraak terms contain the prefix "RS", legal intelligence terms "LI".
"""

RS_IDENTIFIER_ECLI = LI_ECLI = 'ecli'
RS_ISSUED = LI_PUBLICATION_DATE = 'date_published_online'
RS_LANGUAGE = 'language'
RS_CREATOR = LI_ISSUING_INSTITUTION = 'instance'
RS_DATE = LI_ENACTMENT_DATE = 'date_judgement'
RS_ZAAKNUMMER = LI_CASE_NUMBER = 'case_number'
RS_TYPE = 'document_type'
RS_PROCEDURE = 'procedure_type'
RS_SPATIAL = 'jurisdiction_city'
RS_SUBJECT = LI_LAW_AREA = 'domain'
RS_RELATION = 'predecessor_successor_cases'
RS_REFERENCES = 'referenced_legislations_title'
RS_HASVERSION = 'alternative_source_urls'
RS_IDENTIFIER_URL = LI_ORIGINAL_URL = 'source_url'
RS_TITLE = LI_TITLE = 'title'
RS_INHOUDSINDICATIE = LI_SUMMARY = 'summary'
RS_INFO = 'info'
RS_FULLTEXT = 'full_text'
RS_JURISDICTION_COUNTRY = LI_JURISDICTION = 'jurisdiction_country'
RS_SOURCE = LI_DOCUMENT_TYPE = 'source'

# suffix for li attributes:
LI = '_li'