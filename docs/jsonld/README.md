# CLE JSON-LD / knowledge-graph package

Machine-readable artefacts for publishing the `cle_v2` PostgreSQL schema as JSON-LD
and loading it into an RDF knowledge graph. See the full specification and
table-by-table mapping in [`../../docs/cle-jsonld-mapping.md`](../../docs/cle-jsonld-mapping.md).

| File | Purpose |
| --- | --- |
| `cle.context.jsonld` | The shared JSON-LD 1.1 `@context`: prefixes, term mappings, datatypes. Reference it from every emitted document. |
| `cle-vocab.ttl` | The thin `cle:` ontology (RDFS/OWL) with alignments to ELI, SKOS, DC Terms, PROV-O, schema.org and FOAF. |
| `cle-shapes.ttl` | SHACL node/property shapes to validate emitted graphs. |
| `cle-frame.jsonld` | A JSON-LD frame that compacts a Case and its attachments into one document. |
| `catalog.jsonld` | The DCAT catalog: one `dcat:Dataset` per corpus, distributions, SPARQL `dcat:DataService`, publisher and contact point. Placeholder URLs/checksums/licences — replace before publishing. |
| `examples/*.jsonld` | Worked, compacted instances: Rechtspraak case, CJEU case + opinion, ECHR document, a redacted Huurcommissie case, and legislation + provisions. |

## Namespaces

- Ontology / vocabulary: `https://w3id.org/cle/ontology#`
- Instance data: `https://w3id.org/cle/` (e.g. `https://w3id.org/cle/case/ECLI:NL:HR:2024:1`)

`https://w3id.org/cle/` is a *proposed* persistent namespace. Register a
[`w3id.org`](https://github.com/perma-id/w3id.org) redirect (or substitute your own
base) before publishing, so the IRIs are dereferenceable and citable.

## Validate

```bash
# JSON well-formedness
for f in cle.context.jsonld cle-frame.jsonld catalog.jsonld examples/*.jsonld; do
  python3 -c "import json;json.load(open('$f'))" && echo "OK $f"
done

# RDF / SHACL (any engine; example uses pyshacl + rdflib)
pip install pyshacl
pyshacl -s cle-shapes.ttl -df json-ld examples/rs-case.jsonld
pyshacl -s cle-shapes.ttl -df json-ld catalog.jsonld
```

## Conventions used in the examples

- Short `@id`s are resolved against `@base` (`https://w3id.org/cle/`); a real ETL
  SHOULD emit absolute IRIs.
- `rdf:type` uses the `type` alias; `@id` uses the `id` alias.
- Short human-readable fields carry language tags; long/per-language content lives
  in `cle:TextVariant` / `cle:SummaryVersion` nodes.
- `null` values are inert: JSON-LD processors drop them, so they are safe to leave
  in generated output but MUST NOT be relied on.
- `cle:sourceDataset` is an **IRI** to a catalogued corpus (`dataset/{CORPUS}`, defined
  in `catalog.jsonld`); the raw `source`/`sources` token is kept as `cle:sourceCode`
  when it differs from the dataset's identifier.
