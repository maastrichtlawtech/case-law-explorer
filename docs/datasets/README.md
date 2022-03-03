# Datasets

The Case Law Explorer holds two types of data: 

- **Case decisions and opinions**: The full text and meta information of a case, identified by its ECLI number.
- **Case citations**: The link between a case and the cases cited in its decision, identified by the ECLI numbers of the source case and the target case.

Currently, the Case Law Explorer comprises the case law of the Netherlands and that of two European courts. We plan to extend the data to other international courts.

## Dutch Courts

The Dutch case law is collected from different sources.

### Rechtspraak archive

[De Rechtspraak](https://www.rechtspraak.nl/) is a public platform which provides the full texts and meta information of all published Dutch cases. Each case is represented in XML format and the whole collection can be downloaded as a `.zip` archive.

#### Sources

- Original archive: http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip ~5GB
- Sample _small_ (~125k cases): https://surfdrive.surf.nl/files/index.php/s/4qETcxSDuybc4SC ~300MB
- Sample _xsmall_ (~1k cases): https://surfdrive.surf.nl/files/index.php/s/WaEWoCfKlaS0gD0 ~2MB

#### Data format

The following tags are currently extracted from the XML files:

| Name                | Format                             | Definition                                                                                |
|---------------------|------------------------------------|-------------------------------------------------------------------------------------------|
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

- Documentation: https://linkeddata.overheid.nl/service/get-links

## European Court of Human Rights (ECHR)

hey

## Court of Justice of the European Union (CJEU)

hey 
