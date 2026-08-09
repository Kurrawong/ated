# ATED Repository Instructions

This repository publishes the Australian Thesaurus of Education Descriptors (ATED) and its subject categories as SKOS vocabularies for Prez.

## Repository layout

- `raw/xml/` contains source MultiTes XML exports. These source files are intentionally ignored by Git.
- `mappings/` contains the human-readable MultiTes-to-SKOS transformation contracts.
- `metadata/` contains curated RDF scheme metadata that is not derived from XML.
- `src/ated_transform/` contains the shared RDFLib transformation package.
- `shapes/` contains SHACL release requirements.
- `tests/` contains focused fixtures and full-release graph regression tests.
- `scripts/xml_to_skos.py` and `scripts/ated_subjects_to_skos.py` are compatibility wrappers around the shared transformer.
- `scripts/enrich_html.py` post-processes the generated ATED HTML.
- `vocabs/ated.ttl` and `vocabs/ated-sc.ttl` are the checked-in RDF publications.
- `vocabs/ated.html` and `vocabs/ated-sc.html` are checked-in HTML publications.
- `manifest.ttl` and `catalogue.ttl` describe Prez demo publication.
- `scripts/concept_in_hierarchy.py`, `scripts/concept_in_hiearchy_pl.py`, and `scripts/concept_in_hierarchy.rq` are hierarchy-query utilities. Preserve the existing misspelled filename unless explicitly asked to rename it.

## RDF modelling decisions

The main scheme IRI is `https://linked.data.gov.au/def/ated`, with concept IRIs under `https://linked.data.gov.au/def/ated/`.

- Descriptor records become `skos:Concept` resources.
- Use each descriptor's legacy TNR as its concept IRI suffix and as `skos:notation`, typed `xsd:token`.
- Non-descriptor records do not become concepts. Resolve their `USE` relationships and emit their labels as `skos:altLabel` values on descriptor concepts. Ignore non-descriptor TNRs.
- All internal concept relationships, top-concept links, and scheme top-concept links use TNR-based concept IRIs.
- Model source modification dates as `xsd:gYearMonth` when month precision is available and `xsd:gYear` otherwise.
- Link subject categories using `dcterms:subject` and ATED subject-category IRIs.
- Preserve source identifiers and provenance. Each descriptor has a configured `dcterms:source` link to its MultiTes term resource.

The subject-category scheme IRI and namespace are `https://linked.data.gov.au/def/ated/SC` and `https://linked.data.gov.au/def/ated/SC/`.

- Subject categories are top concepts in this scheme.
- Definitions refer explicitly to ATED and call each item a "Subject category", not a "Subject classification".

## Generation

Create the project environment with `uv sync`. Generate both vocabularies and prove graph equivalence to the checked-in release with:

```sh
uv run ated-transform \
  "raw/xml/ATED June2026 with TNRs.xml" \
  --output-dir dist \
  --check-release
```

The legacy wrapper commands remain available when one output is needed:

```sh
uv run python scripts/xml_to_skos.py \
  "raw/xml/ATED June2026 with TNRs.xml" \
  vocabs/ated.ttl

uv run python scripts/ated_subjects_to_skos.py \
  "raw/xml/ATED June2026 with TNRs.xml" \
  vocabs/ated-sc.ttl
```

Run HTML enrichment from the repository root with:

```sh
python3 scripts/enrich_html.py
```

The enrichment step must retain TNR-based anchors, render `dcterms:subject` and `dcterms:modified`, link subjects to `ated-sc.html#NNN`, and synchronize the visible scheme definition from the RDF.

## Validation

Prefer the local RDF toolchain in this order: Kurra for RDF queries, reformatting, and SHACL; then RIOT and Raptor for quick syntax checks. Use RDFLib in Python generation or transformation code.

For changes to generated RDF or generator scripts, run the relevant generation command and at least:

```sh
riot --validate vocabs/ated.ttl
riot --validate vocabs/ated-sc.ttl
rapper -i turtle -c vocabs/ated.ttl
rapper -i turtle -c vocabs/ated-sc.ttl
uv run python -m py_compile scripts/xml_to_skos.py scripts/ated_subjects_to_skos.py scripts/enrich_html.py
uv run python -m unittest discover -s tests -v
kurra shacl validate vocabs/ated.ttl --shacl shapes/ated.shacl.ttl
kurra shacl validate vocabs/ated-sc.ttl --shacl shapes/ated-subject-categories.shacl.ttl
```

Also check the modelling invariants affected by the change, including TNR notation typing, numeric concept IRIs, relationship targets, alternative-label conversion, subject links, and date datatypes. Do not rely only on successful parsing.

For Prez manifest changes, follow the repository README and validate before publication:

```sh
pm validate manifest.ttl
pm load file manifest.ttl /tmp/ated-manifest.trig
```

Publishing to the shared demo database is an external write. Use the dedicated Prez Manifest demo-sync workflow, verify the exact endpoint and credentials, and use the writable SPARQL Graph Store endpoint rather than the public Prez API.

## Git collaboration

Colleagues may update `main` concurrently. Before committing or pushing, run:

```sh
git fetch origin
git status --short --branch
git log --oneline HEAD..origin/main
```

Preserve unrelated local changes. If the remote moved while local work is uncommitted, reconcile deliberately; do not perform a blind pull or destructive reset.

Do not commit raw XML exports, credentials, endpoint secrets, temporary manifest output, or generated cache files.
