#!/usr/bin/env python3
"""Create the ATED subject classification SKOS scheme from ated.ttl."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SCHEME_IRI = "https://linked.data.gov.au/def/ated/SC"
SUBJECT_PATTERN = re.compile(
    r'dcterms:subject\s+"(?P<id>\d{3})\s+(?P<label>[^"]+)"@en'
)


def turtle_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"@en'


def extract_classifications(source: Path) -> dict[str, str]:
    classifications: dict[str, str] = {}
    for match in SUBJECT_PATTERN.finditer(source.read_text(encoding="utf-8")):
        identifier = match.group("id")
        label = match.group("label")
        existing = classifications.get(identifier)
        if existing is not None and existing != label:
            raise ValueError(
                f"Subject classification {identifier} has conflicting labels: "
                f"{existing!r} and {label!r}"
            )
        classifications[identifier] = label

    if not classifications:
        raise ValueError(f"No dcterms:subject classifications found in {source}")
    return classifications


def convert(source: Path, destination: Path) -> None:
    classifications = extract_classifications(source)
    concept_iris = [
        f"atedsc:{identifier}"
        for identifier in sorted(classifications, key=int)
    ]

    lines = [
        f"@prefix atedsc: <{SCHEME_IRI}/> .",
        "@prefix schema: <https://schema.org/> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "atedsc:",
        "    a skos:ConceptScheme ;",
        '    skos:prefLabel "ATED Subject Classifications"@en ;',
        '    skos:definition "Subject classifications for ATED concepts" ;',
        f"    skos:hasTopConcept {', '.join(concept_iris)} ;",
        "    schema:publisher <https://ror.org/012x2n652> ;",
        "    schema:creator <https://ror.org/012x2n652> ;",
        '    schema:createdDate "2026-06-24"^^xsd:date ;',
        '    schema:modifiedDate "2026-06-24"^^xsd:date .',
        "",
        "<https://ror.org/012x2n652>",
        "    a schema:Organization ;",
        '    schema:name "Australian Council for Educational Research" ;',
        '    schema:url "https://www.acer.org/"^^xsd:anyURI .',
    ]

    for identifier in sorted(classifications, key=int):
        label = classifications[identifier]
        lines.extend(
            [
                "",
                f"atedsc:{identifier}",
                "    a skos:Concept ;",
                "    skos:inScheme atedsc: ;",
                "    skos:topConceptOf atedsc: ;",
                f"    skos:prefLabel {turtle_string(label)} ;",
                "    skos:definition "
                f"{turtle_string(f'Subject classification {identifier} {label}')} .",
            ]
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination)


if __name__ == "__main__":
    main()
