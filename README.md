# Australian Thesaurus of Education Descriptors

Vocabulary project modelling, transforming and presenting ATED as a semantic publication.

Both vocabularies are displayed in KurrawongAI's demo [Prez](https://prez.dev/) system at:

* <https://demo.dev.kurrawong.ai/catalogs/exm:demo-vocabs/collections>

## Reproducible transformation

The MultiTes-to-SKOS transformation is split into four reviewable layers:

- `mappings/*.yaml` documents how MultiTes XML fields map to SKOS and names
  the derived rules;
- `metadata/*.ttl` contains curated scheme and organisation metadata that is
  not derived from the XML;
- `src/ated_transform/` implements extraction, reference resolution and the
  named normalisation rules; and
- `shapes/*.shacl.ttl` defines release validation requirements.

Install the pinned project environment:

```sh
uv sync
```

Generate both vocabularies into a staging directory and prove that they are
RDF-graph-equivalent to the checked-in release:

```sh
uv run ated-transform \
  "raw/xml/ATED June2026 with TNRs.xml" \
  --output-dir dist \
  --check-release
```

The graph comparison ignores harmless Turtle ordering and formatting changes
but fails for any added, removed or changed RDF statement.

Validate the generated graphs:

```sh
riot --validate dist/ated.ttl
riot --validate dist/ated-sc.ttl
kurra shacl validate dist/ated.ttl --shacl shapes/ated.shacl.ttl
kurra shacl validate dist/ated-sc.ttl \
  --shacl shapes/ated-subject-categories.shacl.ttl
```

Run the focused transformation tests and full-release regression tests:

```sh
uv run python -m unittest discover -s tests -v
```

The raw XML export remains intentionally untracked. Full-release regression
tests run when it is available locally and are skipped otherwise.

### Mapping boundaries

The YAML files are transformation contracts, not a general-purpose mapping
language. Straight field mappings and policy are declarative. Procedural rules
such as date parsing, inverse `USE` handling, descriptor-reference resolution
and top-concept derivation remain named, tested Python functions. This keeps
the ATED-specific logic visible without requiring RML engine extensions.

## Legacy generation commands

Generate the vocabulary from the MultiTes XML export:

```sh
uv run python scripts/xml_to_skos.py \
  "raw/xml/ATED June2026 with TNRs.xml" \
  vocabs/ated.ttl
```

The legacy entry-point scripts are retained as compatibility wrappers. Run them
inside the project environment with `uv run python`. They now
load the YAML mappings and use the shared RDFLib implementation. The main
vocabulary always includes its configured `dcterms:source` MultiTes links.

## Prez manifest

`manifest.ttl` describes how to load both vocabularies into the
`https://example.com/demo-vocabs` Prez catalogue. Validate it and inspect the
named graphs before publishing:

```sh
pm validate manifest.ttl
pm load file manifest.ttl /tmp/ated-manifest.trig
```

Publish using the internal writable SPARQL Graph Store endpoint and its
credentials, not the public Prez query API:

```sh
pm load sparql manifest.ttl "$DEMO_SPARQL_ENDPOINT" \
  --username "$DEMO_SPARQL_USERNAME"
```

After publishing, verify the deployed ATED version:

```sparql
SELECT ?modified
WHERE {
  GRAPH <https://linked.data.gov.au/def/ated> {
    <https://linked.data.gov.au/def/ated>
      <https://schema.org/dateModified> ?modified .
  }
}
```
