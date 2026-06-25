#!/usr/bin/env python3
"""Create the ATED subject category SKOS scheme from the ATED XML export."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


SCHEME_IRI = "https://linked.data.gov.au/def/ated/SC"
def turtle_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"@en'


def extract_categories(source: Path) -> dict[str, str]:
    categories: dict[str, str] = {}
    root = ET.parse(source).getroot()
    for element in root.iter("SC"):
        identifier, separator, label = element.text.strip().partition(" ")
        if not separator or len(identifier) != 3 or not identifier.isdigit():
            raise ValueError(f"Unrecognized subject category: {element.text!r}")
        existing = categories.get(identifier)
        if existing is not None and existing != label:
            raise ValueError(
                f"Subject category {identifier} has conflicting labels: "
                f"{existing!r} and {label!r}"
            )
        categories[identifier] = label

    if not categories:
        raise ValueError(f"No subject categories found in {source}")
    return categories


def convert(source: Path, destination: Path) -> None:
    categories = extract_categories(source)
    concept_iris = [
        f"atedsc:{identifier}"
        for identifier in sorted(categories, key=int)
    ]

    lines = [
        f"@prefix atedsc: <{SCHEME_IRI}/> .",
        "@prefix schema: <https://schema.org/> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "atedsc:",
        "    a skos:ConceptScheme ;",
        '    skos:prefLabel "ATED Subject Categories"@en ;',
        '    skos:definition "Subject categories for ATED concepts" ;',
        f"    skos:hasTopConcept {', '.join(concept_iris)} ;",
        "    schema:publisher <https://ror.org/012x2n652> ;",
        "    schema:creator <https://ror.org/012x2n652> ;",
        '    schema:createdDate "2026-06-24"^^xsd:date ;',
        '    schema:modifiedDate "2026-06-25"^^xsd:date .',
        "",
        "<https://ror.org/012x2n652>",
        "    a schema:Organization ;",
        '    schema:name "Australian Council for Educational Research" ;',
        '    schema:url "https://www.acer.org/"^^xsd:anyURI .',
    ]

    for identifier in sorted(categories, key=int):
        label = categories[identifier]
        definition_label = label.lower()
        lines.extend(
            [
                "",
                f"atedsc:{identifier}",
                "    a skos:Concept ;",
                "    skos:inScheme atedsc: ;",
                "    skos:topConceptOf atedsc: ;",
                f"    skos:prefLabel {turtle_string(label)} ;",
                "    skos:definition "
                f"{turtle_string(f'Subject category {identifier} in the Australian Thesaurus of Education Descriptors, covering {definition_label}.')} .",
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
