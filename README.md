# Australian Thesaurus of Education Descriptors

Vocabulary project modelling, transforming and presenting ATED as a semantic publication.

The are both displayed in KurrawongAI's demo [Prez](https://prez.dev/) system online at:

* <https://demo.dev.kurrawong.ai/catalogs/exm:demo-vocabs/collections>

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
