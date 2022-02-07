## Datasets
The Case Law Explorer holds two types of data: 
- Case decisions and opinions: The full text and meta information of a case, identified by its ECLI number
- Case citations: The link between a case and the cases cited in its decision, 
identified by the ECLI numbers of the source case and the target case

Currently, the Case Law Explorer comprises the case law of the Netherlands 
and that of two European courts. We plan to extend the data to other international courts.

### Dutch Courts
The Dutch case law is collected from different sources.

#### Rechtspraak archive
[De Rechtspraak](https://www.rechtspraak.nl/) is a public platform which provides the full texts and meta information of all published Dutch cases. 
Each case is represented in XML format and the whole collection can be downloaded as a .zip archive.

Sources: 
- Original archive: http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip ~5GB
- Sample _small_ (~125k cases): https://surfdrive.surf.nl/files/index.php/s/4qETcxSDuybc4SC ~300MB
- Sample _xsmall_ (~1k cases): https://surfdrive.surf.nl/files/index.php/s/WaEWoCfKlaS0gD0 ~2MB

#### Legal Intelligence API
[Legal Intelligence](https://www.legalintelligence.com) is a legal search engine of a private provider which integrates data from different publishers 
and thus enhances the data available at rechtspraak.nl, especially for cases before the year 2000.
The data can be received through their API in JSON (or XML) format.

Current endpoints:
- API endpoint: https://api.legalintelligence.com/
- Documentation: https://www.legalintelligence.com/handleidingen/api-technical-information/

#### Linked Data Overheid (LiDO)
[Linked Data Overheid](https://linkeddata.overheid.nl/) is a public database provided by the Dutch government 
that contains the links between Dutch and European cases and legislation.

Current endpoints:
- http://linkeddata.overheid.nl/service/get-links

### European Court of Human Rights (ECHR)

### Court of Justice of the European Union (CJEU)
