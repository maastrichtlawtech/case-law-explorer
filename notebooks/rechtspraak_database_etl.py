# -*- coding: utf-8 -*-
"""Rechtspraak database ETL.ipynb

Original file is located at
    https://colab.research.google.com/drive/1uzsZBC3hf3CgTs08dDF5EJSHSxBTI1TQ

## Rechtspraak ETL
"""

#!pip install mysql.connector

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

CONNECTION = f'mysql+mysqlconnector://{USERNAME}:{PASSWORD}@{SERVER}:{PORT}/{DATABASE}'

engine = create_engine(CONNECTION, echo=False)#, echo=True)
connection = engine.connect()
query = """SELECT * FROM caselaw.case LIMIT 1;"""
check = pd.read_sql_query(query, con=connection)
check.head()

"""---
### Datasets
"""

df_case_raw = pd.read_csv("https://maastrichtuniversity-ids-open.s3.eu-central-1.amazonaws.com/rechtspraak/case.csv").replace(np.nan, 'NULL', regex=True)
df_country = pd.read_csv("https://maastrichtuniversity-ids-open.s3.eu-central-1.amazonaws.com/rechtspraak/countries.csv").replace(np.nan, 'NULL', regex=True)
df_li_cases = pd.read_csv("https://maastrichtuniversity-ids-open.s3.eu-central-1.amazonaws.com/rechtspraak/legal_intelligence_cases.csv").replace(np.nan, 'NULL', regex=True).drop_duplicates(subset ="ecli")
df_case_opinion = pd.read_csv("https://maastrichtuniversity-ids-open.s3.eu-central-1.amazonaws.com/rechtspraak/case_opinion_from_advocate_general.csv").replace(np.nan, 'NULL', regex=True)
df_case_citation = pd.read_csv("https://maastrichtuniversity-ids-open.s3.eu-central-1.amazonaws.com/rechtspraak/caselaw_citations.csv").replace(np.nan, 'NULL', regex=True)
df_legislation_citation = pd.read_csv("https://maastrichtuniversity-ids-open.s3.eu-central-1.amazonaws.com/rechtspraak/legislation_citations.csv").replace(np.nan, 'NULL', regex=True)

"""---
### Normalization based on constrains
"""

#li formating
for i, li_case in df_li_cases.iterrows():
    ecli = li_case.ecli
    new_ecli = ecli.replace('_', ':')
    df_li_cases.at[i, 'ecli'] = new_ecli

li_intersection = list(set(df_li_cases['ecli']).intersection(set(df_case_raw['case_id'])))

#sample for testing
#sample_size = 500000
#uniques = list(df_case_citation['source_ecli'].sample(n=sample_size, random_state=18))
#uniques.extend(li_intersection)

uniques = list(df_case_citation['source_ecli'])
uniques.extend(li_intersection)

df_case = df_case_raw[df_case_raw['case_id'].isin(uniques)]

##1: legislation citations 
df_legislation_citation = df_legislation_citation[df_legislation_citation['source_ecli'].isin(uniques)].reset_index(drop=True)

##2: case citations 
df_case_citation = df_case_citation[df_case_citation['source_ecli'].isin(uniques)].reset_index(drop=True)

##3: case opinions 
df_case_opinion = df_case_opinion[df_case_opinion['case_id'].isin(uniques)].reset_index(drop=True)

##4: li cases 
df_li_cases = df_li_cases[df_li_cases['ecli'].isin(uniques)].reset_index(drop=True)

print('Number of Cases in\nCases: {}\nLegislation citation: {}\nCase citation: {}\nCase opinion: {}\nLI cases: {}'\
      .format(len(df_case), len(df_legislation_citation), len(df_case_citation), len(df_case_opinion), len(df_li_cases)))

del uniques

"""---
### Utils
"""

import string

def clean_strings(column):
  cleaned = []
  for s in column:
    cleaned.append("".join(filter(lambda char: char in string.printable, s)))
  return [i[0:250] for i in cleaned]

def clean_table_sql(table_name):
  engine.execute("""DELETE FROM `{}`;""".format(table_name))
  engine.execute("""ALTER TABLE `{}` AUTO_INCREMENT = 1;""".format(table_name))

def get_parent_ids(table, column_table, df, column_df):
  """DB table, DB column_table, df: pandas df to look at, column_df"""
  read_all_ids = pd.read_sql("""SELECT id, `{}` FROM `{}` """.format(column_table, table), con=connection)
  id_list = []
  for idx, data in enumerate(df[column_df]):
    id_list.append(read_all_ids[read_all_ids[column_table] == data].id.values[0])
  return id_list


"""---
### Courts
"""

court = pd.DataFrame()
courts_list = df_case_raw.authority.unique()
courts_list = [i.replace('"','-') for i in courts_list]
courts_list.extend(['Other'])

court['name'] = clean_strings(courts_list)
court.loc[:,'type'] = 'NULL'
court.loc[:,'level'] = 'NULL'
court.loc[:,'country'] = 'NULL'
court.loc[:,'language'] = 'NULL' 
court.loc[:,'jurisdiction'] = 'NULL' 
court.loc[:,'law_area'] = 'NULL'
court.loc[:,'authority_level'] = 'NULL'

court.head(2)

court.to_sql('court', con=engine, index=False, if_exists='append', chunksize = 10)
del court

"""---
### Case
"""

map_case = {'date':'date',
            'description':'description',
            'language':'language',
            'venue':'venue',
            'abstract':'abstract',
            'procedure_type':'procedure_type',
            'lodge_date':'lodge_date',
            'alternative_sources':'link',
            'case_id':'ecli'}

case = df_case[map_case.keys()].rename(columns=map_case)
case['name'] = 'NULL'
case['court_id'] = get_parent_ids('court', 'name', df_case, 'authority')
case['date'] = [pd.to_datetime(i, errors='coerce') if i != 'NULL' else pd.to_datetime('1900-01-01 00:00:00') for i in case['date']]
case['lodge_date'] = [pd.to_datetime(i, errors='coerce') if i != 'NULL' else pd.to_datetime('1900-01-01 00:00:00') for i in case['lodge_date']]
case['description'] = clean_strings(case['description'])
case['link'] = clean_strings(case['link'])

case.to_sql('case', con=engine, index=False, if_exists='append', chunksize = 100)

del map_case
del case

"""---
### Case opinion advocate general
"""

map_case_opinion = {'date':'date',
                    'case_number':'case_number',
                    'description':'description',
                    'language':'language',
                    'country':'country',
                    'venue':'venue',
                    'abstract':'abstract',
                    'procedure_type':'procedure_type',
                    'authority':'authority',
                    'case_id':'ecli'}
                    
case_opinion = df_case_opinion[map_case_opinion.keys()].rename(columns=map_case_opinion)
case_opinion['date'] = [pd.to_datetime(i, errors='coerce') if i != 'NULL' else pd.to_datetime('1900-01-01 00:00:00') for i in case_opinion['date']]
case_opinion['abstract'] = clean_strings(case_opinion['abstract'])

case_opinion.to_sql('case_opinion', con=engine, index=False, if_exists='append', chunksize = 100)
del map_case_opinion
del case_opinion

"""---
### Legal Intelligence Cases
"""

map_legal_intelligence_case = {
    'ecli':'ecli',
    'Title':'name',
    'date':'date',
    'abstract':'abstract',
    'LawArea':'subject',
    'Url':'link',
    'DisplayTitle':'DisplayTitle',
    'OriginalUrl':'OriginalUrl',
    'Jurisdiction':'Jurisdiction',
    'DocumentType':'DocumentType',
    'case_number':'CaseNumber',
    'PublicationNumber':'PublicationNumber',
    'IssueNumber':'IssueNumber',
    'lodge_date':'lodge_date',
    'DateAdded':'DateAdded',
    'Sources':'Sources',
    'UrlWithAutoLogOnToken':'UrlWithAutoLogOnToken',
    'authority':'court',
    'DisplaySubtitle':'DisplaySubtitle'
}

legal_intelligence_case = df_li_cases[map_legal_intelligence_case.keys()].rename(columns=map_legal_intelligence_case)
legal_intelligence_case['date'] = [pd.to_datetime(i, errors='coerce') if i != 'NULL' else pd.to_datetime('1900-01-01 00:00:00') for i in df_li_cases['date']]
legal_intelligence_case['lodge_date'] = [pd.to_datetime(i, errors='coerce') if i != 'NULL' else pd.to_datetime('1900-01-01 00:00:00') for i in df_li_cases['lodge_date']]
legal_intelligence_case['DateAdded'] = [pd.to_datetime(i, errors='coerce') if i != 'NULL' else pd.to_datetime('1900-01-01 00:00:00') for i in df_li_cases['DateAdded']]
legal_intelligence_case['name'] = clean_strings(legal_intelligence_case['name'])
legal_intelligence_case['abstract'] = clean_strings(legal_intelligence_case['abstract'])
legal_intelligence_case['DisplayTitle'] = clean_strings(legal_intelligence_case['DisplayTitle'])
legal_intelligence_case['court'] = clean_strings(legal_intelligence_case['court'])
legal_intelligence_case['DisplaySubtitle'] = clean_strings(legal_intelligence_case['DisplaySubtitle'])

legal_intelligence_case.to_sql('legal_intelligence_case', con=engine, index=False, if_exists='append', chunksize = 10)
del map_legal_intelligence_case
del legal_intelligence_case

"""---
### Subjects
"""

subjects_as_list = [list(row.split("; ")) for row in df_case.subject]
unique_subjects = \
    set(list(
        pd.core.common\
            .flatten(subjects_as_list)))
subject = pd.DataFrame()
subject['name'] = clean_strings(list(sorted(unique_subjects)))
subject.loc[:,'standard_name'] = 'NULL'

subject.to_sql('subject', con=engine, index=False, if_exists='append', chunksize = 50)
del subject

"""---
### Case - Subject
"""

df_subjects_case = df_case[['subject','case_id']]
df_subjects_case.loc[:,'subject'] = subjects_as_list
df_subjects_case = df_subjects_case.explode('subject')

parents_ids_subjects = get_parent_ids('subject', 'name', df_subjects_case, 'subject')
parents_ids_cases = get_parent_ids('case', 'ecli', df_subjects_case, 'case_id')
case_subject = pd.DataFrame({'case_id':parents_ids_cases,
                             'subject_id':parents_ids_subjects})

case_subject.to_sql('case_subject', con=engine, index=False, if_exists='append', chunksize = 100)
del df_subjects_case
del case_subject

"""---
### Countries
"""

df_country.loc[:,'language'] = 'NULL'
df_country.loc[:,'eea'] = 0
country = df_country[['country_id','name','language','flag','eu','eea']]\
  .rename(columns={'country_id':'id'})

country.to_sql('country', con=engine, index=False, if_exists='append', chunksize = 50)
del country

"""---
### Case - Country
"""

# df_country_case = df_case[['case_id','country']]
# #df_country_case.loc[:,'country'] = as_list
# df_country_case = df_country_case.explode('country')
# len(df_country_case)

# case_country.to_sql('case_country', con=engine, index=False, if_exists='append', chunksize = 100)

# del df_country_case
# del case_country

"""---
### Case law citation
"""

df_case_citation['case_id'] = get_parent_ids('case', 'ecli', df_case_citation, 'source_ecli')

map_case_citation = {
    'source_ecli':'source_ecli',
    'source_paragraph':'source_paragraph',
    'target_ecli':'target_ecli',
    'target_paragraph':'target_paragraph',
    'case_id':'case_id'
}
case_citation = df_case_citation[map_case_citation.keys()].rename(columns=map_case_citation)

case_citation.head(2)

case_citation.to_sql('case_citation', con=engine, index=False, if_exists='append', chunksize = 100)
del case_citation
#del tuples

"""---
### Legislation citation
"""

parent_ids = get_parent_ids('case', 'ecli', df_legislation_citation, 'source_ecli')
df_legislation_citation['case_id'] = parent_ids
df_legislation_citation.loc[:,'target_name'] = 'NULL'
df_legislation_citation.loc[:,'target_sourcename'] = 'NULL'

map_legislation_citation = {
    'source_ecli':'source_ecli',
    'source_paragraph':'source_paragraph',
    'target_article':'target_id',
    'target_article_paragraph':'target_paragraph',
    'target_name':'target_name',
    'target_sourcename':'target_sourcename',
    'target_article_webpage':'target_link',
    'case_id':'case_id'
}
legislation_citation = df_legislation_citation[map_legislation_citation.keys()].rename(columns=map_legislation_citation)

legislation_citation.to_sql('legislation_citation', con=engine, index=False, if_exists='append', chunksize = 100)

del legislation_citation

"""---
### Case related decision
"""

df_case_related = df_case[['case_id','related_cases']]\
    .rename(columns = {'case_id':'source_ecli', 
                       'related_cases': 'referencing_case_ecli'})
df_case_related['case_id'] = get_parent_ids('case', 'ecli', df_case_related, 'source_ecli')
df_case_related.loc[:,'referenced_case_ecli'] = 'NULL'

map_case_related_decision = {
    'source_ecli':'source_ecli',
    'referencing_case_ecli':'referencing_case_ecli',
    'referenced_case_ecli':'referenced_case_ecli',
    'case_id':'case_id'
    }

case_related_decision = df_case_related[map_case_related_decision.keys()].rename(columns=map_case_related_decision)

case_related_decision.to_sql('case_related_decision', con=engine, index=False, if_exists='append', chunksize = 100)
del case_related_decision