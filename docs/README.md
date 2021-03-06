[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)

# Case Law Explorer
Materials for building a network analysis software platform for analyzing Dutch and European court decisions. This repository builds on the work by Dafne van Kuppevelt of the Netherlands e-Science Centre [NLeSC/case-law-app](https://github.com/NLeSC/case-law-app).

## Quickstart
Yeah about that.... Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Turpis egestas pretium aenean pharetra. Orci eu lobortis elementum nibh tellus molestie. Vulputate dignissim suspendisse in est. 

Vel pharetra vel turpis nunc. Malesuada nunc vel risus commodo. Nisi vitae suscipit tellus mauris. Posuere morbi leo urna molestie at elementum eu. Urna duis convallis convallis tellus. Urna molestie at elementum eu. Nunc sed blandit libero volutpat.

## ETL pipeline
See [Data extraction](/elt/)

## Datasets
Let's describe the current datasets, the reasons we use them and maybe future plans?

### Rechtspraak Archive
Description of Rechtspraak Archive

Current sources: 
- Original archive: http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip ~5GB
- Sample _small_ (~125k cases): https://surfdrive.surf.nl/files/index.php/s/4qETcxSDuybc4SC ~300MB
- Sample _xsmall_ (~1k cases): https://surfdrive.surf.nl/files/index.php/s/WaEWoCfKlaS0gD0 ~2MB

### Legal Intelligence API
Description of Legal Intelligence API

Current endpoints:
- Original endpoint: https://api.legalintelligence.com/
- Documentation: https://www.legalintelligence.com/handleidingen/api-technical-information/

## Taxonomy
|                 Term                |                                         Definition                                        |
|:-----------------------------------:|:-----------------------------------------------------------------------------------------:|
| ECLI (European Case Law Identifier) | Unique identifier for court decisions in Europe                                           |
| Issued date                         | Date of document publication                                                              |
| Enactment Date                      | Date of court decision                                                                    |
| Language                            | Language of jurisdiction to which case belongs                                            |
| Creator                             | Name of instance (court)                                                                  |
| Zaaknummer                          | Case number, for internal use by courts                                                   |
| Case type                           | 'uitspraak' (decision) or 'conclusie' (opinion)                                           |
| Procedure type                      | e.g. summary proceedings                                                                  |
| Spatial                             | Court location (municipality)                                                             |
| Subject                             | Domain (area of the law) applicable to case                                               |
| Relation                            | Predecessor and successor cases (in case of appeal, cassation, preliminary decisions etc) |
| References                          | Title of applicable legislation                                                           |
| Inhoudsindicatie                    | Case summary                                                                              |

## License 
This work is licensed under a [Creative Commons Attribution-NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en) 

[![License Image: CC BY-NC 4.0](https://licensebuttons.net/l/by-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)


