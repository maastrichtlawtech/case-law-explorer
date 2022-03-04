# Datasets

The Case Law Explorer holds two types of data: 

- **Case decisions and opinions**: The full text and meta information of a case, identified by its ECLI number.
- **Case citations**: The link between a case and the cases cited in its decision, identified by the ECLI numbers of the source case and the target case.

Currently, the Case Law Explorer comprises the case law of the Netherlands and that of two European courts. We plan to extend the data to other international courts.

## Dutch courts

The Dutch case law is collected from different sources.

### Rechtspraak archive

[De Rechtspraak](https://www.rechtspraak.nl/) is a public platform which provides the full texts and meta information of all published Dutch cases. Each case is represented in XML format and the whole collection can be downloaded as a `.zip` archive.

#### Sources

- Documentation: https://www.rechtspraak.nl/Uitspraken/paginas/open-data.aspx
- Original archive: http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip ~5GB
- Sample _small_ (~125k cases): https://surfdrive.surf.nl/files/index.php/s/4qETcxSDuybc4SC ~300MB
- Sample _xsmall_ (~1k cases): https://surfdrive.surf.nl/files/index.php/s/WaEWoCfKlaS0gD0 ~2MB

#### Extraction 

The Rechtspraak extraction scripts (found under [`data_extraction/caselaw/rechtspraak/`](https://github.com/maastrichtlawtech/case-law-explorer/tree/master/data_extraction/caselaw/rechtspraak)) are executing as it follows: 

- [`rechtspraak_dump_downloader.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/rechtspraak/rechtspraak_dump_downloader.py) downloads the latest available archive found on the Rechtspraak website at https://www.rechtspraak.nl/Uitspraken/paginas/open-data.aspx.
- [`rechtspraak_dump_unzipper.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/rechtspraak/rechtspraak_dump_unzipper.py) unzips the downloaded `OpenDataUitspraken.zip` archive and all the archives found in its sub-directories (_i.e._ years and months).
- [`rechtspraak_metadata_dump_parser.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/rechtspraak/rechtspraak_metadata_dump_parser.py) parses the data from the unzipped XML files, and saves them in CSV files under the structure defined in the **Data format** section.

#### Data format

The following tags are currently extracted from the XML files:

| Name                | Format                             | Definition                                                                                |
|:--------------------|:----------------------------------|:------------------------------------------------------------------------------------------|
| ecli                | String                             | ECLI (European Case Law Identifier): unique identifier for court decisions in Europe      |
| identifier          | String                             | URL to original document by publisher                                                     |
| issued              | String / yyyy-mm-dd                | Date of document publication                                                              |
| language            | String / "nl"                      | Language of jurisdiction to which case belongs                                            |
| creator             | String                             | Name of instance (court)                                                                  |
| spatial             | String                             | Court location (municipality)                                                             |
| date                | String / yyyy-mm-dd                | Date of court decision                                                                    |
| zaaknummer          | String                             | Case number, for internal use by courts (main identifier prior to introduction of ECLI)   |
| type                | String / "uitspraak" / "conclusie" | Document type: decision/opinion                                                           |
| procedure           | String[]                           | Procedure type (e.g. summary proceedings)                                                 |
| subject             | String / "domain; subdomain"       | Domain (area of the law) applicable to case                                               |
| relation            | String[]                           | Predecessor and successor cases (in case of appeal, cassation, preliminary decisions etc) |
| references          | String[]                           | Title of applicable legislation                                                           |
| hasVersion          | String[]                           | References to other publications                                                          |
| title               | String                             | Title of case                                                                             |
| inhoudsindicatie    | XML                                | Case summary                                                                              |
| uitspraak/conclusie | XML                                | Full text of case decision/opinion                                                        |

### Legal Intelligence API

[Legal Intelligence](https://www.legalintelligence.com) is a legal search engine of a private provider which integrates data from different publishers and thus enhances the data available at rechtspraak.nl, especially for cases before the year 2000. The data can be received through their API in JSON (or XML) format.

#### Sources

- API endpoint: https://api.legalintelligence.com/
- Documentation: https://www.legalintelligence.com/handleidingen/api-technical-information/

#### Extraction 

The Legal Intelligence extraction script ([`legal_intelligence_extractor.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/legal_intelligence/legal_intelligence_extractor.py)) operates as it follows:

- Builds the query URL using the endpoint https://api.legalintelligence.com/, the query string, and the filters (*e.g.* jurisdiction, court, country).
- Retrieves the data from the URL, cleans it based on a few rules (*e.g.* court duplicates, dates), and stores it a `DataFrame`. It repeats this step for each page returned by the API.
- Finally, it stores the data using the [`Storage` object](/api/storage). 

#### Data format

The following fields are currently extracted from the JSON objects:  

| Name                | Type / Format | Definition                                                                                |
|:--------------------|:--------------|:------------------------------------------------------------------------------------------|
| Id                  | String        | Internal document ID                                                                      |
| Title               | String        | Title of case                                                                             |
| DisplayTitle        | String        | Internal title of document entry                                                          |
| DisplaySubtitle     | String        | Internal subtitle of document entry                                                       |
| Summary             | String        | Case summary                                                                              |
| Url                 | String        | URL to document entry in Legal Intelligence                                               |
| OriginalUrl         | String        | URL to original document by publisher                                                     |
| Jurisdiction        | String / "Nederland" | Country of jurisdiction                                                                   |
| DocumentType        | String / "Rechtspraak"       | Source of case                                                                            |
| LawArea             | String[]      | Domains (area of the law) applicable to case                                              |
| IssuingInstitution  | String        | Name of instance (court)                                                                  |
| CaseNumber          | String        | Case number, for internal use by courts (main identifier prior to introduction of ECLI)   |
| PublicationNumber   | String        | Internal document id of publisher                                                         |
| IssueNumber         | String        | References to other publications                                                          |
| PublicationDate     | Int / yyyyMMdd| Date of document publication                                                              |
| EnactmentDate       | Int / yyyyMMdd| Date of court decision                                                                    |
| DateAdded           | Int / yyyyMMdd| Date document added to Legal Intelligence                                                 |
| Sources             | String[]      | References to other publications                                                          |

### Linked Data Overheid (LiDO)

[Linked Data Overheid](https://linkeddata.overheid.nl/) is a public database provided by the Dutch government that contains the links between Dutch and European cases and legislation.

#### Sources

- API Endpoint: http://linkeddata.overheid.nl/service/get-links
- Documentation: https://linkeddata.overheid.nl/front/portal/services

#### Extraction 

The LIDO extraction script ([`rechtspraak_citations_extractor_incremental.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/citations/rechtspraak_citations_extractor_incremental.py)) it follows the following steps:

- Builds the query URL using the API endpoint http://linkeddata.overheid.nl/service/get-links and a few filters such as `start`, `rows`, `output`.
- The responses from the API are being cleaned and stored in a `DataFrame`. This is repeated from all the pages returned by the API. 
- The returned data is being divided into `caselaw` and `legislation` citations.
- Finally, the data is stored using the [`Storage` object](/api/storage). 

#### Data format

The following fields are expected to be in the CSV files storing the citations:

| Name        | Format | Definition                           |
|:------------|:-------|:-------------------------------------|
| Source ECLI | String | ECLI of the case that cites          |
| Target ECLI | String | ECLI of the case that is being cited |

## European courts

We are making efforts to include in our project European and international courts as well. So far we are working to add this European courts to our codebase.

### European Court of Human Rights (ECHR)

> [!ATTENTION|label:WORK IN PROGRESS]
> The ECHR extraction, transformation, and loading script are still **work in progress**! This is an overview of the current data format and legacy extraction methods.

The [ECHR](https://www.echr.coe.int/Pages/home.aspx?p=home) is dealing with cases alleging that a state has breached human rights agreed in the European Convention on Human Rights. The [HUDOC database](https://www.echr.coe.int/Pages/home.aspx?p=caselaw/HUDOC&c=) provides access to the caselaw of the ECHR.  

#### Sources

- Documentation: https://www.echr.coe.int/Documents/HUDOC_Manual_ENG.PDF
- HUDOC UI: https://hudoc.echr.coe.int/
- HUDOC Endpoint: 
 ```
 https://hudoc.echr.coe.int/app/query/results?query=(contentsitename=ECHR) AND (documentcollectionid2:"JUDGMENTS" OR documentcollectionid2:"COMMUNICATEDCASES")&select=itemid,applicability,application,appno,article,conclusion,decisiondate,docname,documentcollectionid, documentcollectionid2,doctype,doctypebranch,ecli,externalsources,extractedappno,importance,introductiondate, isplaceholder,issue,judgementdate,kpdate,kpdateAsText,kpthesaurus,languageisocode,meetingnumber, originatingbody,publishedby,Rank,referencedate,reportdate,representedby,resolutiondate, resolutionnumber,respondent,respondentOrderEng,rulesofcourt,separateopinion,scl,sharepointid,typedescription, nonviolation,violation&sort=itemid Ascending&start=0&length=2
 ```

#### Extraction

The ECHR extraction script ([`ECHR_metadata_harvester.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/echr/ECHR_metadata_harvester.py)) operates the following steps:

- Builds the query URL with the endpoint http://hudoc.echr.coe.int/app/query/, filters such as `contentsitename` or `documentcollectionid2`, and arguments such as `start` and `length`.
- Fetches the data from the API and stores it in a `DataFrame` for each page returned.
- Filters only the cases that are in English.
- Finally, the data is stored using the [`Storage` object](/api/storage). 

#### Data format

The following fileds are expected to be found in the CSV files storing ECHR data:

| Name                | Format   | Definition                                       |
|:--------------------|:---------|:-------------------------------------------------|
| itemid              | String   | Unique identifier                                |
| applicability       | String   |                                                  |
| application         | String   |                                                  |
| appno               | String   | Application number                               |
| article             | String   | Alleged violated articles                        |
| conclusion          | String   | Violated/Non-violated articles                   |
| docname             | String   | Name of the case                                 |
| doctype             | String   | Type of document                                 |
| doctypebranch       | String   |                                                  |
| ecli                | String   | Unique identifier for court decisions in Europe  |
| importance          | Number   |                                                  |
| isplaceholder       | Boolean  |                                                  |
| judgementdate       | Date     | Date of judgement                                |
| kpdate              | Date     | Date of judgement in 12-hours format             |
| kpdateAsText        | String   | Date of judgement as string                      |
| kpthesaurus         | String   |                                                  |
| languageisocode     | String   | Language of case                                 |
| originatingbody     | Number   |                                                  |
| Rank                | Number   |                                                  |
| representedby       | String   | Representation of the case                       |
| respondent          | String   | Defender of the case                             |
| respondentOrderEng  | Number   | Defender unique identifier                       |
| separateopinion     | Boolean  |                                                  |
| sharepointid        | Number   | Internal identifier                              |
| typedescription     | Number   |                                                  |
| violation           | String   | Violated articles                                |
| typedescription     | Number   |                                                  |
| violation           | String   |                                                  |

### Court of Justice of the European Union (CJEU)

> [!ATTENTION|label:WORK IN PROGRESS]
> The CJEU extraction, transformation, and loading script are still **work in progress**! This is an overview of the current data format and legacy extraction methods.

The [CJEU](https://european-union.europa.eu/institutions-law-budget/institutions-and-bodies/institutions-and-bodies-profiles/court-justice-european-union-cjeu_en) is an European court that makes sure the law is applied in the same way in all EU countries. CJEU cases' metadata and content can be retrieved from [CELLAR](https://data.europa.eu/data/datasets/sparql-cellar-of-the-publications-office?locale=en), an European service that provides data through a SPARQL API. 

#### Sources

- API Endpoint: https://publications.europa.eu/webapi/rdf/sparql
- Documentation: https://op.europa.eu/documents/10530/676542/ao10463_annex_17_cellar_dissemination_interface_en.pdf

#### Extraction

The CJEU extraction script ([`cellar_extraction.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_extraction/caselaw/cellar/cellar_extraction.py)) follows the methodology:

- It queries SPARQL endpoint https://publications.europa.eu/webapi/rdf/sparql for all the ECLIs available in the CELLAR that are related to the CJEU. 
- For each ECLI returned, it queries the API for the metadata of each case, and stores it in a `DataFrame`. 
- The `DataFrame`'s data is exported as a JSON file using the [`Storage` object](/api/storage).

#### Data format

These fields are expected to be found in the JSON files that store the CJEU data: 

| Name                                     | Type    | Definition                      |
|:-----------------------------------------|:--------|:--------------------------------|
| _key                                     | String  | Unique identifier               |
| Legal resource has type of act           | String  | Type of document                |
| Case law originates in country           | String  | Country of decision             |
| Legal resource is about subject matter   | String  | Subject of case                 |
| ECLI                                     | String  |                                 |
| Reference to provisions of national law  | RDF     | Reference to the the judgement  |
| Publication reference of Court decision  | RDF     | Reference to the decision       |
| Celex identifier                         | String  | Celex identifier                |
| Local identifier                         | String  | Local identifier                |
| Sector identifier                        | Number  | Sector identifier               |
| Type of legal resource                   | String  | Legal resource type             |
| Year of the legal resource               | Number  | Legal resource year             |
| Work is created by agent (AU)            | URL     | Link to the legal agent         |
| Legacy date of creation of work          | Date    | System date                     |
| Date of document                         | Date    | Document date                   |
| Identifier of document                   | String  | Celex unique identifier         |
| Work title                               | String  | Case title                      |
| CMR creation date                        | Date    | Creation date                   |
| last CMR modification date               | Date    | Last updated date               |
| Case law delivered by national court     | URL     | Link to the court               |
| Case law based on a legal instrument     | URL     | Link to the legal instrument    |
| Parties of the case law                  | RDF     | Reference to the parties        |

