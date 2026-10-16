# `cle_v2` → JSON-LD / knowledge graph: mapping specification

Status: proposal v0.1 · 2026-10-16
Artifacts: [`docs/jsonld/`](jsonld/) — context, vocabulary, SHACL shapes, frame,
DCAT catalog, examples.

---

## 1. Scope

This specification defines how to publish the **`cle_v2`** schema as JSON-LD so that it
can be loaded into an RDF triple store (GraphDB/Jena/Blazegraph/etc.) **and** projected
into a property graph (Neo4j/etc.) without changing the serialised form.

Covered: every `cle_v2` table. Not covered: the `legacy` and `public` schemas, and the
`cle_v2._v_*` views (they are SQL projection helpers; the graph is built from the base
tables — see §10.10).

Out of scope for the graph content itself: embedding vectors, `tsvector` indexes and
operator-only tables (§7).

---

## 2. Decisions

| Question | Decision |
| --- | --- |
| Ontology | Reuse ELI, SKOS, DC/DCTerms, DCAT, PROV-O, schema.org, FOAF, org, OWL-Time; add a thin `cle:` extension for what has no home. |
| Target store | Store-agnostic JSON-LD 1.1 (valid for RDF and cleanly projectable to a property graph). |
| Base IRI | `https://w3id.org/cle/`, keyed by **natural identifiers** (ECLI, CELEX, item_id, external_ref, lido_id, BWB code, ISO codes), falling back to surrogate `bigint`. |
| Translations | Hybrid: `rdf:langString` for short fields (titles, labels, section texts); **per-language nodes** (`cle:TextVariant`, `cle:SummaryVersion`) for full text and summaries. |
| Embeddings | Excluded from the graph; only model metadata is emitted. |
| PII / depublication | Redact directly identifying fields, mark redaction explicitly; keep depublicated content with a status marker. |
| Relations | Explicit reification nodes (no RDF-star). |
| Scope | `cle_v2` tables only. |

---

## 3. The model at a glance

```
                         dcterms:subject          skos:Concept
        ┌───────────────────────────────►  cle:Domain
        │
   cle:Case  ──cle:court──►  cle:Court ──cle:inJurisdiction──► cle:Jurisdiction
        │                    │  └─cle:parentCourt─┘
        │                    └── (cle:Judge committed via cle:CaseJudgeRole)
        │
        ├─cle:hasDocument──►  cle:CaseDocument  ─┬─ cle:RechtspraakDocument
        │                        (1 per source)  ├─ cle:EchrDocument
        │                                         ├─ cle:CjeuDocument
        │                                         ├─ cle:AdvocateGeneralOpinion
        │                                         └─ cle:{Disciplinary, Geschillencommissie,
        │                                                Gip, Huurcommissie, Kifid, Skgz}Document
        ├─cle:hasTextVariant──► cle:TextVariant      (per language × source)
        ├─cle:hasSummaryVersion──► cle:SummaryVersion (per language × scope × model)
        ├─cle:hasSegment──► cle:Segment
        ├─cle:hasCitation──► cle:Citation ──► cle:Case (target)
        ├─cle:hasCaseLawReference──► cle:CaseLawReference ──► cle:Legislation / cle:LegalProvision
        ├─cle:hasPartyRole──► cle:CasePartyRole ──► cle:Party
        ├─cle:hasJudgeRole──► cle:CaseJudgeRole ──► cle:Judge
        ├─cle:hasEntityMention──► cle:EntityMention ──skos:exactMatch──► external entity
        ├─cle:hasExternalAuthority / hasFormalRelation / hasPublication  (Rechtspraak only)
        └─cle:inSnapshot──► cle:NetworkSnapshot ──► cle:NetworkMetric / cle:CaseCluster

   cle:Legislation (eli:Legislation) ──cle:isPartOf──► cle:Legislation (parent)
        ├─cle:hasAlias──► cle:LegislationAlias
        └─◄─cle:inLegislation── cle:LegalProvision ──cle:parentProvision──► cle:LegalProvision
```

`cle:Case` is the hub: one node per `cases` row, plus one `cle:CaseDocument` per
source-specific `*_document` row, plus the language and relation nodes.

---

## 4. IRI minting rules

Base `B = https://w3id.org/cle/`. `{case}` below is the case IRI (see row 1).
URL-encode path segments that contain characters outside the RFC 3986 `pchar` set
(ECLI colons `:` are legal in a path segment and stay as-is; `#`, `?`, `/`, `%` must be
percent-encoded).

| Node | IRI template | Fallback order |
| --- | --- | --- |
| Case | `B case/{ecli}` | `ecli` → `celex_id` → `item_id` → `external_ref` (encoded) → `id` (surrogate) |
| Court | `B court/{code}` | `code` → `court/id/{id}` |
| Jurisdiction | `B jurisdiction/{iso_code}` | always |
| Judge | `B judge/{id}` | surrogate (names are not unique) |
| Party | `B party/{id}` | surrogate |
| Court formation | `B formation/{code}` | always |
| Domain | `domain.uri` verbatim | else `B domain/{scheme}/{id}` |
| Document type / procedure type / instance | `B concept/{table}/{code}` | else `.../id/{id}` |
| Language | `http://lexvo.org/id/iso639-1/{iso_code}` | reuse Lexvo; do not mint |
| Legislation | `http://wetten.overheid.nl/id/{identifier}` for `scheme='bwb'`; the ELI IRI for EU acts; else `B legislation/{lido_id}` | `lido_id` → scheme-specific → `B legislation/{scheme}/{identifier}` |
| Legal provision | `B provision/{lido_id}` | `lido_id` (unique) |
| Legislation alias | `{legislation-iri}/alias/{id}` | always |
| Case document | `{case}/document/{SOURCE}` | `{case}/document/{id}` for CJEU national |
| ECHR document | `B document/echr/{item_id}` | `item_id` (its PK) |
| Text variant | `{case}/text/{language}/{source}` | `source` = `case_text.source`; ECHR secondary text uses `HUDOC_SECONDARY` |
| Summary version | `{case}/summary/{id}` | surrogate |
| Segment | `B segment/{id}` | surrogate (`segment_hash` is only unique per case) |
| Citation | `B citation/{id}` | surrogate |
| Case-law reference | `B lawref/{id}` | surrogate |
| Case party role | `{case}/party/{party_id}/{role}/{ordinal}` | always |
| Case judge role | `{case}/judge/{judge_id}/{role}` | always |
| Entity mention | `{case}/mention/{id}` | external identity kept as `skos:exactMatch` |
| Network snapshot | `B snapshot/{id}` | surrogate |
| Network metric | `B snapshot/{snapshot_id}/metric/{case_id}` | always |
| Case cluster | `B cluster/{id}` | surrogate |
| External authority / formal relation / publication / case link | `{case}/authority/{id}`, `{case}/formalrelation/{id}`, `{case}/publication/{id}`, `B caselink/{id}` | surrogate |

Surrogate IRIs are stable for a given database but **not** portable; prefer natural
keys wherever a row has one. When rows are merged/deduplicated later, `owl:sameAs`
links can reconcile the two forms.

---

## 5. Multilingual strategy

Three tiers, matching the three shapes already present in the schema:

1. **Controlled vocabulary labels** — `language`, `domain_label`, court names, concept
   names. Emitted as per-language `rdfs:label` / `skos:prefLabel` / `skos:altLabel`
   (JSON-LD `@container: @language` language maps). Language itself is a Lexvo IRI.
2. **Short in-row fields** — `cases.title`, `legislation.title`, `echr_document.docname`,
   section texts. Emitted as `rdf:langString` literals, tagged from the row's language
   (`cases.language_iso`, `case_text.language`, `domain_label.language`, `_lang_map`).
3. **Full text and summaries** — `case_text`, `case_summary_version`,
   `echr_document_secondary_text`. Emitted as **nodes** (`cle:TextVariant`,
   `cle:SummaryVersion`) keyed by language so per-language provenance (source,
   `extractor_version`, `is_stub`, `version_number`, `is_current`, models) is preserved.

`_lang_map` (HUDOC ↔ ISO) does not create nodes: it enriches the Lexvo language concept
with `cle:hudocCode` (e.g. Lexvo `…/nl` → `hudocCode "DUT"`). ISO codes are normalised
to lower-case and validated against the `language` seed (24 EU languages, BCP 47
language subtags).

---

## 6. Reification of qualified relations

Every n-ary relation becomes a first-class node with qualifiers, plus (where useful) a
convenience shortcut edge on the case for property-graph convenience. The reification
node remains authoritative; shortcut edges are derived and may be dropped.

| Table | Node class | Shortcut |
| --- | --- | --- |
| `case_citation` | `cle:Citation` | `cle:cites` on `cle:Case` |
| `case_law_reference` | `cle:CaseLawReference` | none (references carry roles) |
| `case_party` | `cle:CasePartyRole` | none |
| `case_judge` | `cle:CaseJudgeRole` | none |
| `case_entity` | `cle:EntityMention` | none |
| `lido_link` | `cle:CaseLink` | none |
| `rs_document_formal_relation` | `cle:FormalRelation` | none |
| `rs_document_external_authority` | `cle:ExternalAuthority` | none |
| `rs_document_publication` | `cle:Publication` | none |

This keeps weights, roles, `version_date`, `source_dataset`, `context_segment_id`,
`aanleg`/`gevolg` and extraction provenance on the edge — all of which a plain triple
would lose.

---

## 7. Excluded from the graph

| Content | Column(s) | Reason |
| --- | --- | --- |
| Embeddings | `case_segment.embedding`, `case_summary_version.summary_embedding`, `case_text.summary_embedding` | 768-dim `vector`; not RDF-native. Emit `cle:embeddingModel` only; vectors stay in pgvector for ANN search. |
| Full-text indexes | `case_text.fulltext_tsv`, `summary_tsv` | Generated `tsvector`; derivable, not data. |
| Operational tables | `migration_manifest`, `search_query_log` | ETL/search-audit state and user telemetry; not legal content. (`search_query_log.clicked_case_ids` is out of scope.) |
| Derived | `case_citation_counts` is folded into the `cle:Case` node (not a node of its own); `_lang_map` enriches language concepts (§5). |

---

## 8. Privacy, depublication and access rights

- **Huurcommissie PII** (`submitter`, `city`, `postal_code`, `residence_address`) is
  **not** emitted. The document node carries `cle:redacted true` and
  `cle:redactedFields [...]`, plus `dcterms:accessRights` and `dcterms:license`. The
  SHACL shape `cle:HuurcommissieDocumentShape` enforces this.
- **Depublicated** Rechtspraak decisions: still emitted, with
  `cle:opendataStatus "depublicated"` and `dcterms:accessRights`; retrieval decision is
  left to the query layer.
- **Personal names in the source** (`judge.full_name`, `party.canonical_name`,
  `echr_document.respondent`) are emitted as they appear in the public source, since
  they are already public; no additional redaction is applied.

---

## 9. Provenance, licensing and FAIR

- **Provenance**: every extractor/version/timestamp column maps onto PROV-O
  (`prov:generatedAtTime`, `prov:wasGeneratedBy`) plus `cle:extractorVersion` /
  `cle:*Model`; `cle:sourceDataset` names the originating pipeline
  (`RECHTSPRAAK`, `HUDOC`, `CELLAR`, `LIDO`, the tribunal sources, `HUDOC_SECONDARY`, …).
- **Findable**: persistent `w3id.org` IRIs; natural-key identifiers; a **DCAT catalog**
  ([`docs/jsonld/catalog.jsonld`](jsonld/catalog.jsonld)) with one `dcat:Dataset` per
  corpus, each carrying publisher, license, spatial/temporal coverage, update cadence
  and an NDJSON-LD distribution.
- **Accessible**: serve JSON-LD at each IRI via content negotiation
  (`Accept: application/ld+json`); export bulk NDJSON-LD for the whole corpus; a
  `dcat:DataService` advertises the SPARQL endpoint.
- **Interoperable**: reuse of ELI/SKOS/DCAT/PROV/schema.org; SHACL shapes published;
  the catalog conforms to DCAT.
- **Reusable**: explicit `dcterms:license` / `dcterms:accessRights`; the vocabulary is
  versioned (`owl:versionInfo`).

### 9.1 Source corpora → `dcat:Dataset`

`cle:sourceDataset` is an **object property** pointing at a catalogued corpus
(`B dataset/{CORPUS}`). The raw value of the `source`/`sources` column is preserved as
`cle:sourceCode` where it differs from the dataset's `dcterms:identifier`. Dataset nodes
list their accepted raw tokens in `cle:sourceCode`.

| `dcat:Dataset` | `dcterms:identifier` | raw tokens seen in `cle_v2` |
| --- | --- | --- |
| `dataset/RECHTSPRAAK` | `RECHTSPRAAK` | `RECHTSPRAAK`, `Rechtspraak` |
| `dataset/HUDOC` | `HUDOC` | `HUDOC`, `ECHR_OPEN_DATA`, `HUDOC_SECONDARY` |
| `dataset/CELLAR` | `CELLAR` | `CELLAR`, `CELLAR_ITEM`, `INFOCURIA_BLOB_HTML`, `INFOCURIA_BLOB` |
| `dataset/LIDO` | `LIDO` | `LIDO`, `lido_postgres` |
| `dataset/TUCHTRECHT` | `TUCHTRECHT` | `TUCHTRECHT`, `Tuchtrecht` |
| `dataset/GESCHILLENCOMMISSIE` | `GESCHILLENCOMMISSIE` | `GESCHILLENCOMMISSIE` |
| `dataset/GIP` | `GIP` | `GIP` |
| `dataset/HUURCOMMISSIE` | `HUURCOMMISSIE` | `HUURCOMMISSIE`, `Huurcommissie` |
| `dataset/KIFID` | `KIFID` | `KIFID`, `Kifid` |
| `dataset/SKGZ` | `SKGZ` | `SKGZ` |

> **Rule:** wherever a mapping below says a `source` / `sources` column →
> `cle:sourceDataset`, emit the resolved dataset **IRI**; also emit `cle:sourceCode`
> with the raw token whenever it differs from that dataset's `dcterms:identifier`
> (e.g. `source='CELLAR_ITEM'` → `cle:sourceDataset dataset/CELLAR` +
> `cle:sourceCode "CELLAR_ITEM"`).

---

## 10. Table-by-table mapping

Legend: **→** maps to. Every table also implicitly gets `dcterms:identifier` derived
from its natural key where one exists.

### 10.1 Reference and controlled vocabularies

#### `jurisdiction` → `cle:Jurisdiction`
IRI `B jurisdiction/{iso_code}`.

| column | property |
| --- | --- |
| `iso_code` | `cle:isoCode` (also `dcterms:identifier`) |
| `name` | `skos:prefLabel` (langString, `en`) |
| `type` | `cle:level` |

#### `court` → `cle:Court`
IRI `B court/{code}` or `B court/id/{id}`.

| column | property |
| --- | --- |
| `code` | `cle:courtCode`, `dcterms:identifier` |
| `name` | `skos:prefLabel` |
| `level` | `cle:level` |
| `jurisdiction_id` | `cle:inJurisdiction` → Jurisdiction |
| `parent_court_id` | `cle:parentCourt` → Court (`org:subOrganizationOf`) |

#### `court_formation` → `cle:CourtFormation` (skos:Concept)
IRI `B formation/{code}`. `code` → `skos:notation`; `label` → `skos:prefLabel`;
`judge_count` → `cle:judgeCount` (integer); `skos:inScheme "scheme/formation"`.

#### `document_type`, `procedure_type`, `instance` → skos:Concept
IRI `B concept/{table}/{code}`. `code` → `skos:notation`; `name` → `skos:prefLabel`;
`skos:inScheme` = `scheme/{table}`.

#### `language` → `cle:Language` (skos:Concept)
IRI reused from Lexvo: `http://lexvo.org/id/iso639-1/{iso_code}`. `iso_code` →
`skos:notation`; `name` → `skos:prefLabel` (en); `skos:inScheme` = `scheme/language`.
Do **not** mint a `cle:` language IRI — reuse Lexvo so the value space is aligned with
other datasets.

#### `_lang_map` → enrichment of `cle:Language`
`hudoc` → `cle:hudocCode` on the Lexvo concept for `iso`. No node of its own.

#### `domain` → `cle:Domain` (skos:Concept)
IRI `domain.uri` when non-null, else `B domain/{scheme}/{id}`. `scheme` → `cle:scheme`;
`name` → `skos:prefLabel`; `uri` → the node IRI **and** `skos:exactMatch` to it (so the
concept keeps a stable local identity even when an external URI is present);
`parent_id` → `skos:broader`.

#### `domain_label` → labels of `cle:Domain`
One node per `(domain_id, language)`: `label` → `skos:prefLabel` added to the domain's
language map; `language` selects the tag.

#### `legislation_alias` → `cle:LegislationAlias`
IRI `{legislation}/alias/{id}`. `alias` → `cle:aliasText` **and** `skos:altLabel`
(langString); `source` → `cle:sourceDataset`; `legislation_id` → `cle:aliasOf`; the
parent legislation also gets `cle:hasAlias`.

### 10.2 Core case

#### `cases` → `cle:Case`
IRI per §4 row 1.

| column | property |
| --- | --- |
| `ecli` | `cle:ecli`, `dcterms:identifier` |
| `celex_id` | `cle:celexId` |
| `item_id` | `cle:itemId` |
| `external_ref` | `cle:externalRef` |
| `title` | `dcterms:title` (langString tag = `language_iso`) |
| `date_decision` | `cle:dateDecision` (`xsd:date`, ∈ `dcterms:date`) |
| `date_published` | `schema:datePublished` (`xsd:date`) |
| `court_id` | `cle:court` → Court |
| `language_iso` | `dcterms:language` → Lexvo IRI |
| `document_type_id` | `cle:documentType` → Concept |
| `procedure_type_id` | `cle:procedureType` → Concept |
| `instance_id` | `cle:instance` → Concept |
| `case_number` | `cle:caseNumber` |
| `importance` | `cle:importance` (`xsd:integer`) |
| `is_landmark` | `cle:isLandmark` (`xsd:boolean`) |
| `created_at` | `dcterms:created` (`xsd:dateTime`) |
| `updated_at` | `dcterms:modified` (`xsd:dateTime`) |
| `sources` (text[]) | `cle:sourceDataset` (IRI, repeated) + `cle:sourceCode` (§9.1) |

Inverse links are not stored; they are produced by the child nodes
(`cle:hasDocument`, `cle:hasTextVariant`, …).

#### `case_citation_counts` → properties of `cle:Case`
`cites_count` → `cle:citesCount`; `cited_by_count` → `cle:citedByCount`;
`updated_at` → `cle:countsUpdatedAt`. Not a separate node.

#### `court` seed rows / `jurisdiction` seed rows
The `INSERT` seeds simply become the corresponding `cle:Court` / `cle:Jurisdiction`
nodes; `code`-keyed tribunal bodies and Kifid child courts are ordinary Court nodes
linked by `cle:parentCourt`.

### 10.3 Source-specific documents (one `cle:CaseDocument` per row)

All document nodes carry `cle:sourceCase` → `cle:Case` and `cle:sourceDataset`.

#### `rs_document` → `cle:RechtspraakDocument`
IRI `{case}/document/RECHTSPRAAK`.

| column | property |
| --- | --- |
| `date_decision` | `cle:dateDecision` |
| `document_type` | `cle:documentTypeText` |
| `instance` | `cle:instanceText` |
| `domains` (text[]) | `cle:domainText` (repeated) |
| `source` | `cle:sourceDataset` |
| `jurisdiction_country` | `cle:jurisdictionCountry` |
| `procedure_type` | `cle:procedureTypeText`¹ |
| `url_publication` | `cle:publicationUrl` |
| `legal_provisions` (text[]) | `cle:legalProvisionText` (repeated) |
| `predecessor_successor_cases` | `cle:predecessorSuccessorCases` |
| `date_published` | `schema:datePublished` |
| `date_issued` | `cle:dateIssued` |
| `date_modified` | `cle:sourceModified` |
| `title` | `dcterms:title` |
| `language` | `dcterms:language` |
| `access_rights` | `dcterms:accessRights` |
| `zittingsplaats` | `cle:zittingsplaats` |
| `replaces_identifier` | `cle:replacesIdentifier` |
| `creator_uri` | `dcterms:creator` (IRI) |
| `vindplaatsen` (text[]) | `cle:vindplaats` (repeated) |
| `subject_uris` (text[]) | `dcterms:subject` (IRIs) |
| `zaaknummer` | `cle:zaaknummer` |
| `opendata_status` | `cle:opendataStatus` |
| `created_at` / `updated_at` | `dcterms:created` / `dcterms:modified` |

¹ `procedure_type` is a text column but is a known controlled value; where it matches
the procedure-type scheme, emit the Concept IRI via `cle:procedureType` as well.

#### `rs_document_external_authority` → `cle:ExternalAuthority`
IRI `{case}/authority/{id}`. `kind` → `cle:kind`; `name` → `cle:authority`;
`article` → `cle:article`; `raw` → `cle:raw`; `created_at` → `dcterms:created`; parent
document gets `cle:hasExternalAuthority`.

#### `rs_document_formal_relation` → `cle:FormalRelation`
IRI `{case}/formalrelation/{id}`. `target_ecli` → `cle:targetEcli` (IRI if resolvable,
else literal); `target_identifier` → `cle:targetIdentifier`; `relation_type` →
`cle:relationType`; `aanleg` → `cle:aanleg`; `name` → `skos:prefLabel`; `disposition` →
`cle:disposition`; `gevolg` → `cle:gevolg`.

#### `rs_document_publication` → `cle:Publication`
IRI `{case}/publication/{id}`. `kind` → `cle:kind`; `journal_abbr` → `cle:journalRefs`;
`year` → `schema:datePublished` (year); `locator` → `cle:locator`; `annotator` →
`cle:annotator`; `raw` → `cle:raw`.

#### `echr_document` → `cle:EchrDocument`
IRI `B document/echr/{item_id}`.

| column | property |
| --- | --- |
| `item_id` | `cle:itemId` (+ IRI) |
| `language` | `dcterms:language` |
| `extractedappno` | `cle:extractedApplicationNumber` |
| `docname` | `cle:documentName` |
| `doctype` | `cle:echrDocType` |
| `doctype_branch` | `cle:echrDocTypeBranch` |
| `judgement_date` / `reference_date` | `cle:judgementDate` / `cle:referenceDate` |
| `article` | `cle:article` |
| `conclusion` | `cle:conclusion` |
| `violation` / `nonviolation` | `cle:violation` / `cle:nonviolation` |
| `respondent` | `cle:respondent` |
| `originating_body` | `cle:originatingBody` (integer) |
| `represented_by` | `cle:representedBy` |
| `published_by` | `cle:publishedBy` |
| `rules_of_court` | `cle:rulesOfCourt` |
| `applicability` | `cle:applicability` |
| `separate_opinion` | `cle:separateOpinion` |
| `issue` | `cle:issue` |
| `importance` | `cle:importance` |
| `rank` | `cle:rank` |
| `scl` | `cle:scl` |
| `external_sources` | `cle:externalSources` |
| `judgement_year` | `cle:judgementYear` |
| `created_at` / `updated_at` | `dcterms:created` / `dcterms:modified` |

#### `echr_document_appno` → `cle:ApplicationNumber`
IRI `{echr-doc}/appno/{appno}/{source}`. `appno` → `cle:applicationNumber`;
`source` → `cle:sourceDataset`; `created_at` → `dcterms:created`; parent gets
`cle:hasApplicationNumber`.

#### `echr_document_article` → `cle:EchrArticleApplication`
IRI `{echr-doc}/article/{kind}/{article_code}`. `kind` → `cle:articleKind`
(`applied`/`violation`/`nonviolation`); `article_code` → `cle:articleCode`;
`protocol` → `cle:protocol`; `raw` → `cle:raw`; parent gets `cle:hasArticleApplication`.

#### `echr_document_secondary_text` → `cle:TextVariant`
IRI `{case}/text/{echr-doc.language}/HUDOC_SECONDARY`. `fulltext` → `cle:fullText`
(langString); `created_at` → `dcterms:created`; `cle:sourceDataset "HUDOC_SECONDARY"`.
The case also gets `cle:hasTextVariant`.

#### `echr_extractor_segments` → `cle:EchrExtractorAnalysis`
IRI `{echr-doc}/analysis/{item_id}`. `parser_mode` → `cle:parserMode`; `error` →
`cle:parserError`; the nine section columns (`procedure`, `facts`, `complaints`, `law`,
`operative`, `subject_matter`, `court_assessment`, `separate_opinion`, `appendix`) →
`cle:procedureSection`, `cle:factsSection`, `cle:complaintsSection`, `cle:lawSection`,
`cle:operativeSection`, `cle:subjectMatterSection`, `cle:courtAssessmentSection`,
`cle:separateOpinionSection`, `cle:appendixSection` (langStrings); `num_sections` →
`cle:numSections`; `segmented_at` → `prov:generatedAtTime`; `extractor_version` →
`cle:extractorVersion`; parent gets `cle:hasExtractorAnalysis`.

#### `cjeu_document` → `cle:CjeuDocument`
IRI `{case}/document/CELLAR`. Columns map 1:1 under `cle:` names:
`celex_id`, `ecli`, `sector`, `case_number`, `formation_id` → `cle:formation`,
`proc_type`, `procedure_result`, `date_lodged`, `cellar_uri`, `work_uri`,
`journal_refs`, `erecueil_ref`, `local_identifier`, `dossier_uri`,
`citations_extra_info`, `national_judgement_xml`; `dossier_parent_case_id` →
`cle:parentCase`.

#### `cjeu_ag_opinion` → `cle:AdvocateGeneralOpinion`
IRI `opinion_uri` if set, else `{case}/opinion/{id}`. `advocate_general` →
`cle:advocateGeneral`; `opinion_uri` → node IRI and `cle:opinionUri`;
`delivered_date` → `cle:deliveredDate`; `parent_case_id` → `cle:parentCase`;
`case_id` → `cle:sourceCase`. `type` also includes `cle:CaseDocument`.

#### `cjeu_national_document` → `cle:CjeuNationalDocument`
IRI `{case}/national/{id}`. All `national_*` columns map to the matching `cle:` term
(`national_court_uri` → `cle:nationalCourtUri`, …); `case_id` → `cle:sourceCase`.

#### Tribunal documents (1:1 with a case)
All are `cle:CaseDocument` subclasses; IRI `{case}/document/{SOURCE}`,
`cle:sourceDataset` = the source.

| Table | Class | Column → property (beyond `case_id`/timestamps) |
| --- | --- | --- |
| `disciplinary_document` | `cle:DisciplinaryDocument` | `domain`→`cle:domain`, `creator`→`cle:creatorName`, `seat`→`cle:seat`, `case_number`→`cle:caseNumber`, `date_decision`→`cle:dateDecision`, `date_modified`→`cle:sourceModified`, `decision_type`→`cle:decisionType`, `subject`→`cle:domainText`, `sub_subject`→`cle:subSubject`, `version`→`cle:version`, `page_url`/`xml_url`/`pdf_url`→`cle:pageUrl`/`cle:xmlUrl`/`cle:pdfUrl`, `source`→`cle:sourceDataset` |
| `gc_document` | `cle:GeschillencommissieDocument` | `committee`→`cle:committee`, `committee_slug`→`cle:committeeSlug`, `category`→`cle:category`, `year`→`cle:judgementYear`, `decision_type`→`cle:decisionType`, `outcome`→`cle:outcome`, `reference_code`→`cle:referenceCode`, `title`→`dcterms:title`, `source_url`→`cle:sourceUrl`, `last_modified`→`cle:sourceModified` |
| `gip_document` | `cle:GipDocument` | `dispute_type`→`cle:disputeType`, `type`→`cle:kind`, `date_decision`→`cle:dateDecision`, `subject`→`cle:domainText`, `pension_fund`→`cle:pensionFund`, `date_submitted`→`cle:dateSubmitted`, `date_published`→`schema:datePublished`, `summary`/`case_summary`→`cle:summaryText`/`cle:caseSummary`, `pdf_url`→`cle:pdfUrl` |
| `huurcommissie_document` | `cle:HuurcommissieDocument` | `case_number`→`cle:caseNumber`, `date_decision`→`cle:dateDecision`, `date_published`→`schema:datePublished`, `objected_title`→`cle:objectedTitle`, `decision`→`cle:decision`, `residence_type`→`cle:residenceType`, `residence_points`→`cle:residencePoints`, `law_article`→`cle:lawArticle`, `amount_before_verdict`/`amount_after_verdict`→`cle:amountBeforeVerdict`/`cle:amountAfterVerdict`, `temporarily_decreased_rent`/`leges_conviction`→booleans, `pdf_url`→`cle:pdfUrl`, **PII redacted (§8)** |
| `kifid_document` | `cle:KifidDocument` | `case_number`→`cle:caseNumber`, `nature`→`cle:nature`, `category`→`cle:category`, `authority`→`cle:authority`, `target_group`→`cle:targetGroup`, `defendant`→`cle:defendant`, `tags`→`cle:tag`, `summary`→`cle:summaryText`, `detail_url`/`pdf_url`→`cle:detailUrl`/`cle:pdfUrl`, `is_published`→`cle:isPublished` |
| `skgz_document` | `cle:SkgzDocument` | `case_number`→`cle:caseNumber`, `date_decision`→`cle:dateDecision`, `date_published`→`schema:datePublished`, `outcome`→`cle:outcome`, `category`/`category_all`→`cle:category`/`cle:categoryAll`, `summary`→`cle:summaryText`, `pdf_url`→`cle:pdfUrl`, `related_case_numbers`→`cle:relatedCaseNumber` |

### 10.4 Text, segments, summaries

#### `case_text` → `cle:TextVariant`
IRI `{case}/text/{language}/{source}`; unique key preserved.

| column | property |
| --- | --- |
| `language` | `dcterms:language` |
| `fulltext` | `cle:fullText` (langString) |
| `summary` | `cle:summaryText` (langString) |
| `summary_source` | `cle:summarySource` |
| `summary_embedding` | **excluded** (§7); `cle:embeddingModel` kept |
| `embedding_model` | `cle:embeddingModel` |
| `source` | `cle:sourceDataset` |
| `text_format` | `cle:textFormat` |
| `missing_reasons` | `cle:missingReasons` |
| `created_at` / `updated_at` | `dcterms:created` / `dcterms:modified` |
| `is_stub` | `cle:isStub` (xsd:boolean) |
| `fulltext_tsv` / `summary_tsv` | **excluded** (§7) |

The case node gets `cle:hasTextVariant`.

#### `case_summary_version` → `cle:SummaryVersion`
IRI `{case}/summary/{id}`. `language` → `dcterms:language`; `summary_text` →
`cle:summaryText`; `summary_embedding` **excluded**, `embedding_model` →
`cle:embeddingModel`; `summarization_model` → `cle:summarizationModel`;
`segment_scope` → `cle:segmentScope`; `version_number` → `cle:versionNumber`;
`is_current` → `cle:isCurrent`; `generation_source` → `cle:generationSource`;
`rejected_at` → `cle:rejectedAt`; `rejection_reason` → `cle:rejectionReason`;
`parent_version_id` → `prov:wasRevisionOf`; `created_at` → `dcterms:created`. The case
gets `cle:hasSummaryVersion`.

#### `case_segment` → `cle:Segment`
IRI `B segment/{id}`. `language` → `dcterms:language`; `segment_type` →
`cle:segmentType`; `segment_index` → `cle:segmentIndex`; `segment_text` → `cle:fullText`
(langString); `segment_hash` → `cle:segmentHash`; `embedding`/**excluded**,
`embedding_model` → `cle:embeddingModel`; `extractor_version` → `cle:extractorVersion`;
`created_at` → `dcterms:created`. The case gets `cle:hasSegment`.

### 10.5 Relations, references, roles, mentions

#### `case_citation` → `cle:Citation`
IRI `B citation/{id}`. `source_case_id` → `cle:sourceCase`; `target_case_id` →
`cle:targetCase`; `target_ecli_raw` → `cle:targetEcliRaw`; `target_celex_raw` →
`cle:targetCelexRaw`; `relation_type` → `cle:relationType`; `source_dataset` →
`cle:sourceDataset`; `weight` → `cle:weight`; `context_segment_id` →
`cle:contextSegment`; `is_cross_jurisdiction` → `cle:isCrossJurisdiction`;
`extractor_at` → `prov:generatedAtTime`; `extractor_version` → `cle:extractorVersion`.
Source case gets `cle:hasCitation` and the shortcut `cle:cites` → target case.

#### `case_law_reference` → `cle:CaseLawReference`
IRI `B lawref/{id}`. `case_id` → `cle:sourceCase`; `legislation_id` →
`cle:targetLegislation`; `provision_id` → `cle:targetProvision`; `raw_scheme` →
`cle:rawScheme`; `raw_resource` → `cle:rawResource`; `raw_subdivision` →
`cle:rawSubdivision`; `raw_label_id` → `cle:rawLabelId`; `raw_reference` →
`cle:rawReference`; `version_date` → `cle:versionDate`; `role` → `cle:referenceRole`;
`source_dataset` → `cle:sourceDataset`; `created_at` → `dcterms:created`. Case gets
`cle:hasCaseLawReference`.

#### `case_party` → `cle:CasePartyRole`
IRI `{case}/party/{party_id}/{role}/{ordinal}`. `case_id` → `cle:sourceCase`;
`party_id` → `cle:party`; `role` → `cle:role`; `ordinal` → `cle:ordinal`. Case gets
`cle:hasPartyRole`.

#### `case_judge` → `cle:CaseJudgeRole`
IRI `{case}/judge/{judge_id}/{role}`. `case_id` → `cle:sourceCase`; `judge_id` →
`cle:judge`; `role` → `cle:role`. Case gets `cle:hasJudgeRole`.

#### `judge` → `cle:Judge`
IRI `B judge/{id}`. `full_name` → `foaf:name`; `aliases` → `skos:altLabel` (one per
language, untagged); `court_id` → `cle:court`.

#### `party` → `cle:Party`
IRI `B party/{id}`. `canonical_name` → `cle:canonicalName`; `aliases` →
`skos:altLabel`; `role_class` → `cle:partyRoleClass`; `country_iso` → `cle:countryIso`.

#### `case_entity` → `cle:EntityMention`
IRI `{case}/mention/{id}`. `case_id` → `cle:sourceCase`; `entity_type` →
`cle:entityType`; `canonical_name` → `cle:canonicalName`; `surface_form` →
`cle:surfaceForm`; `uri` → `skos:exactMatch` (external identity — **not** the node
IRI, so mentions keep a stable local IRI); `char_start`/`char_end` →
`cle:charStart`/`cle:charEnd`; `confidence` → `cle:confidence`. Case gets
`cle:hasEntityMention`.

#### `lido_link` → `cle:CaseLink`
IRI `B caselink/{id}`. `source_case_id` → `cle:sourceCase`; `target_case_id` →
`cle:targetCase`; `source_ecli`/`target_ecli` → `cle:sourceEcli`/`cle:targetEcli`;
`source_uri`/`target_uri` → `cle:sourceUri`/`cle:targetUri`; `target_provision_id` →
`cle:targetProvision`; `link_type` → `cle:linkType`; `fetched_at` →
`prov:generatedAtTime`.

### 10.6 Legislation

#### `legislation` → `cle:Legislation` (also `eli:Legislation`, `skos:Concept`)
IRI per §4. `identifier` → `dcterms:identifier`; `scheme` → `cle:scheme`; `title` →
`dcterms:title` (langString); `jurisdiction_id` → `cle:inJurisdiction`;
`document_type` → `cle:documentTypeText`; `enacted_date` → `cle:enactedDate`
(`eli:date_document`); `lido_id` → `cle:lidoId`; `jc_id` → `cle:jcId`;
`snapshot_date` → `cle:snapshotDate`.

#### `legal_provision` → `cle:LegalProvision` (`eli:LegalResourceSubdivision`)
IRI `B provision/{lido_id}`. `legislation_id` → `cle:inLegislation`; `parent_id` →
`cle:parentProvision` (∈ `dcterms:isPartOf`); `element_type` → `cle:elementType`;
`article_label` → `cle:articleLabel`; `title` → `dcterms:title`; `paragraph` →
`cle:paragraph`; `text` → `cle:provisionText` (langString); `bwb_label_id` →
`cle:bwbLabelId`; `lido_id` → `cle:lidoId`; `jc_id` → `cle:jcId`; `effective_from` /
`effective_to` → `cle:effectiveFrom` / `cle:effectiveTo`; `snapshot_date` →
`cle:snapshotDate`.

#### `lido_link` resolved provision URLs
The `rs_v_document_law_reference` view computes `legal_provision_url`
(`http://wetten.overheid.nl/id/{bwb}/{date}/0`) and `legal_provision_url_lido`
(`http://linkeddata.overheid.nl/terms/bwb/id/{bwb}/{label}/{date}/{date}`). These are
the recommended **target IRIs** for the corresponding `cle:LegalProvision` /
`cle:CaseLawReference` nodes; when a provision row exists, prefer its `B provision/{lido_id}`
IRI and keep the view URL as `rdfs:seeAlso`.

### 10.7 Network analysis

#### `network_snapshot` → `cle:NetworkSnapshot`
IRI `B snapshot/{id}`. `snapshot_date` → `cle:snapshotDate`; `description` →
`dcterms:description`; `node_count`/`edge_count` → `cle:nodeCount`/`cle:edgeCount`;
`created_at` → `dcterms:created`.

#### `case_network_metric` → `cle:NetworkMetric`
IRI `B snapshot/{snapshot_id}/metric/{case_id}`. `snapshot_id` → `cle:inSnapshot`;
`case_id` → `cle:metricForCase`; `in_degree`/`out_degree` → `cle:inDegree`/
`cle:outDegree`; `pagerank`, `betweenness`, `hub_score`, `authority_score`,
`eigenvector` → same-named `cle:` properties. Optional mirror on the case node within
a named graph for the snapshot.

#### `case_cluster` → `cle:CaseCluster`
IRI `B cluster/{id}`. `snapshot_id` → `cle:inSnapshot`; `algorithm` → `cle:algorithm`;
`label` → `skos:prefLabel`; `size` → `cle:size`.

#### `case_cluster_membership` → `cle:clusterMember`
Cluster gets `cle:clusterMember` → case (repeatable). No independent node.

### 10.8 Other

#### `party`, `judge`, `court`, `jurisdiction`, `domain`, `legislation`, `legal_provision`
See above.

### 10.9 Excluded tables

`migration_manifest`, `search_query_log` — operational (§7).

### 10.10 Views (not converted)

`case_text_canonical`, `echr_v_document_with_text`, `echr_v_judgments_decisions`,
`rs_v_document_law_reference`, `rs_v_document_legal_provisions`,
`rs_v_document_with_text`, and the function `rs_date_to_iso` are SQL-level projections
of the base tables. They are **not** emitted; equivalent shapes are produced by the
graph queries/SHACL. The one exception worth reusing is the `legal_provision_url`
computation (§10.6).

---

## 11. Property-graph projection

For Neo4j/etc., the same JSON-LD projects mechanically:

- each `@id` → a node; `@type` → one or more labels (last path segment, e.g. `Case`,
  `Citation`);
- `@id`-valued properties → typed relationships (edge type = the property's local
  name, e.g. `HAS_CITATION`, `CITES`, `COURT`);
- literal properties → node/edge properties; `rdf:langString` → a property set per
  language (`title_nl`, `title_en`) or a map property;
- reification nodes stay nodes (they are where `weight`, `role`, `versionDate`,
  `sourceDataset` live), so qualified edges survive.

The convenience `cle:cites` edge is duplicated data; keep it for traversal and treat
`cle:Citation` nodes as the source of truth.

Named graphs (RDF) / labels (property graph) recommended: one per
`cle:sourceDataset`, plus one per `cle:NetworkSnapshot`.

---

## 12. Validation & tooling

- **SHACL**: `docs/jsonld/cle-shapes.ttl` (validate with `pyshacl`, Jena `shacl`, or
  TopBraid). Includes shapes for the DCAT catalog and for the `cle:sourceDataset` →
  `dcat:Dataset` linkage.
- **JSON-LD**: any 1.1 processor can expand/compact; the frame
  `docs/jsonld/cle-frame.jsonld` compacts a Case and its attachments into one document.
- **Round-trip check**: expand each example, re-compact against the context, and
  expand again — the expanded forms must be identical (catches context mistakes).

---

## 13. Open items / recommendations

1. **Register `w3id.org/cle/`** (or pick a project domain) before publishing, so the
   IRIs are persistent and dereferenceable (FAIR F1).
2. **DCAT catalog** ✅ done — see [`docs/jsonld/catalog.jsonld`](jsonld/catalog.jsonld):
   a `dcat:Catalog`, one `dcat:Dataset` per corpus (§9.1), a `dcat:Distribution`
   per dataset, a `dcat:DataService` for the SPARQL endpoint, and an `org:Organization`
   publisher + contact point. **Fill in the placeholders** before publishing: the
   publisher organisation (`org/BISS`), the contact e-mail, the `data.example.org`
   dump/landing URLs, real `dcat:byteSize` and SPDX checksums, per-source licenses,
   and the update cadence per corpus.
3. **ELI for EU legislation**: the `celex` → ELI IRI resolution
   (`http://data.europa.eu/eli/…`) currently relies on `cjeu_document.work_uri` /
   `cellar_uri`; where those are absent, fall back to the minted `cle:legislation/…`
   IRI and record `cle:celexId`.
4. **Judgment date vs. decision date** differ across sources; the current mapping uses
   `cle:dateDecision` for the decision date and `cle:dateIssued`/`schema:datePublished`
   for the rest. Confirm this is the intended semantics.
5. **Multi-language titles for CJEU**: `cases.title` is often English only; the
   per-language titles live in Cellar expressions. If those are ingested later, promote
   titles to language maps on the Case.
6. **Segment IRIs** are surrogate (no natural key); if segments are ever re-generated,
   consider keying on `{case}/{language}/{segment_hash}` for stability.
