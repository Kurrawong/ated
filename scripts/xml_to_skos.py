#!/usr/bin/env python3
"""Convert the ATED XML export to SKOS Turtle."""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


BASE_IRI = "https://linked.data.gov.au/def/ated/"
SCHEME_IRI = "https://linked.data.gov.au/def/ated"
MULTITES_TERM_URL = (
    "https://cunningham.acer.edu.au/multites2007/mtwdk.exe"
    "?k=default&l=60&w={tnr}&n=1&s=5&t=2"
)
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

SCHEME_DEFINITION = """The Australian Thesaurus of Education Descriptors (ATED) has been the definitive reference on Australian terminology in the area of education since 1979. It reflects terminology used to describe research and practice in Australian education.

Developed and maintained by ACER Cunningham Library and updated every six months, ATED is the indispensible tool for indexing and searching Australian education literature.

ATED is used to index the Australian Education Index, Education Research Theses, Database of Research on International Education, Blended, Online Learning and Distance Education research bank, Indigenous Education Research Database and the ACER library catalogue and can also be used to consult these databases."""


def turtle_string(value: str, language: str | None = None) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    literal = f'"{escaped}"'
    return f"{literal}@{language}" if language else literal


def modified_date(value: str) -> str:
    """Normalize an amendment date without inventing precision."""
    compact = re.sub(r"\s+", " ", value.strip())
    year_only = re.fullmatch(r"(\d{4})", compact)
    if year_only:
        return f"{turtle_string(year_only.group(1))}^^xsd:gYear"

    month_year = re.fullmatch(r"([A-Za-z]+)\s*(\d{2}|\d{4})", compact)
    if not month_year:
        raise ValueError(f"Unrecognized amendment date: {value!r}")
    month_name, year_text = month_year.groups()
    try:
        month = MONTHS[month_name.lower()]
    except KeyError as error:
        raise ValueError(f"Unrecognized month in amendment date: {value!r}") from error
    year = int(year_text)
    if len(year_text) == 2:
        year += 1900 if year >= 50 else 2000
    normalized = f"{year:04d}-{month:02d}"
    return f"{turtle_string(normalized)}^^xsd:gYearMonth"

def concept_iri(tnr: str) -> str:
    """Return the compact IRI for a descriptor concept TNR."""
    if not tnr:
        raise ValueError("Concept TNR cannot be empty")
    return f":{tnr}"


def multites_term_iri(tnr: str) -> str:
    """Return the legacy MultiTes resource IRI for a descriptor TNR."""
    if not tnr:
        raise ValueError("MultiTes Term Number cannot be empty")
    return f"<{MULTITES_TERM_URL.format(tnr=tnr)}>"


def iri_for(label: str, tnrs: dict[str, str]) -> str:
    try:
        return concept_iri(tnrs[label])
    except KeyError as error:
        raise ValueError(f"Unknown descriptor reference: {label!r}") from error


def subject_iri(classification: str) -> str:
    match = re.fullmatch(r"(\d{3})\s+.+", classification.strip())
    if not match:
        raise ValueError(f"Unrecognized subject classification: {classification!r}")
    return f"atedsc:{match.group(1)}"


def add_statement(
    statements: list[tuple[str, list[str]]], predicate: str, objects: list[str]
) -> None:
    if objects:
        statements.append((predicate, objects))


def render_subject(subject: str, statements: list[tuple[str, list[str]]]) -> str:
    lines = [subject]
    for index, (predicate, objects) in enumerate(statements):
        terminator = " ." if index == len(statements) - 1 else " ;"
        lines.append(f"    {predicate} {', '.join(objects)}{terminator}")
    return "\n".join(lines)


def convert(
    source: Path, destination: Path, include_multites_provenance: bool = False
) -> None:
    root = ET.parse(source).getroot()
    records = root.findall("CONCEPT")
    descriptors = {
        record.findtext("DESCRIPTOR"): record
        for record in records
        if record.find("DESCRIPTOR") is not None
    }

    tnrs = {
        descriptor: record.findtext("TNR").strip()
        for descriptor, record in descriptors.items()
        if record.findtext("TNR")
    }
    missing_tnrs = sorted(set(descriptors) - set(tnrs))
    if missing_tnrs:
        raise ValueError(f"Descriptors missing TNRs: {missing_tnrs}")

    tnr_labels: dict[str, list[str]] = defaultdict(list)
    for descriptor, tnr in tnrs.items():
        tnr_labels[tnr].append(descriptor)
    duplicate_tnrs = {
        tnr: labels for tnr, labels in tnr_labels.items() if len(labels) > 1
    }
    if duplicate_tnrs:
        details = "; ".join(
            f"{tnr}: {labels}" for tnr, labels in sorted(duplicate_tnrs.items())
        )
        raise ValueError(f"Duplicate concept TNRs: {details}")

    non_descriptors: dict[str, list[str]] = defaultdict(list)
    for record in records:
        label = record.findtext("NON-DESCRIPTOR")
        if label:
            for preferred in record.findall("USE"):
                if preferred.text not in descriptors:
                    raise ValueError(
                        f"Non-descriptor {label!r} refers to unknown descriptor "
                        f"{preferred.text!r}"
                    )
                non_descriptors[preferred.text].append(label)

    top_concepts = [
        concept_iri(tnrs[descriptor])
        for descriptor, record in descriptors.items()
        if not record.findall("BT")
    ]

    prefixes = [
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix : <https://linked.data.gov.au/def/ated/> .",
        "@prefix atedsc: <https://linked.data.gov.au/def/ated/SC/> .",
        "@prefix cs: <https://linked.data.gov.au/def/ated> .",
        "@prefix id: <http://id.loc.gov/vocabulary/identifiers/> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix schema: <https://schema.org/> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
    ]
    if include_multites_provenance:
        prefixes.insert(5, "@prefix prov: <http://www.w3.org/ns/prov#> .")

    blocks = [
        "\n".join(prefixes),
        render_subject(
            "cs:",
            [
                ("a", ["skos:ConceptScheme"]),
                (
                    "skos:prefLabel",
                    [
                        turtle_string(
                            "Australian Thesaurus of Education Descriptors", "en"
                        )
                    ],
                ),
                (
                    "skos:definition",
                    [turtle_string(SCHEME_DEFINITION, "en")],
                ),
                ("skos:hasTopConcept", top_concepts),
                ("schema:publisher", ["<https://ror.org/012x2n652>"]),
                ("schema:creator", ["<https://ror.org/012x2n652>"]),
                ("schema:dateCreated", ['"2026-06-24"^^xsd:date']),
                ("schema:dateModified", ['"2026-07-23"^^xsd:date']),
                ("schema:identifier", ['"9780864316813"^^id:isbn']),
            ],
        ),
        render_subject(
            "<https://ror.org/012x2n652>",
            [
                ("a", ["schema:Organization"]),
                (
                    "schema:name",
                    [turtle_string("Australian Council for Educational Research")],
                ),
                ("schema:url", ['"https://www.acer.org/"^^xsd:anyURI']),
            ],
        ),
    ]

    for descriptor, record in descriptors.items():
        statements: list[tuple[str, list[str]]] = [
            ("a", ["skos:Concept"]),
            ("rdfs:isDefinedBy", ["cs:"]),
            ("skos:inScheme", ["cs:"]),
            ("skos:prefLabel", [turtle_string(descriptor, "en")]),
            (
                "skos:definition",
                [
                    turtle_string(
                        f"{descriptor} is a concept in the Australian Thesaurus "
                        "of Education Descriptors",
                        "en",
                    )
                ],
            ),
        ]
        if include_multites_provenance:
            statements.insert(
                1,
                ("prov:wasDerivedFrom", [multites_term_iri(tnrs[descriptor])]),
            )

        add_statement(
            statements,
            "skos:notation",
            [
                f"{turtle_string(element.text.strip())}^^xsd:token"
                for element in record.findall("TNR")
                if element.text
            ],
        )

        alt_labels = [element.text for element in record.findall("UF")]
        alt_labels.extend(non_descriptors.get(descriptor, []))
        add_statement(
            statements,
            "skos:altLabel",
            [turtle_string(label, "en") for label in dict.fromkeys(alt_labels)],
        )
        add_statement(
            statements,
            "skos:scopeNote",
            [turtle_string(element.text, "en") for element in record.findall("SN")],
        )
        add_statement(
            statements,
            "skos:broader",
            [iri_for(element.text, tnrs) for element in record.findall("BT")],
        )
        add_statement(
            statements,
            "skos:narrower",
            [iri_for(element.text, tnrs) for element in record.findall("NT")],
        )
        add_statement(
            statements,
            "skos:related",
            [iri_for(element.text, tnrs) for element in record.findall("RT")],
        )
        add_statement(
            statements,
            "dcterms:subject",
            [subject_iri(element.text) for element in record.findall("SC")],
        )
        add_statement(
            statements,
            "dcterms:modified",
            [modified_date(element.text) for element in record.findall("AD")],
        )
        if not record.findall("BT"):
            statements.insert(3, ("skos:topConceptOf", ["cs:"]))

        blocks.append(render_subject(concept_iri(tnrs[descriptor]), statements))

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--multites-provenance",
        action="store_true",
        help="add a prov:wasDerivedFrom link to each legacy MultiTes term resource",
    )
    args = parser.parse_args()
    convert(args.source, args.destination, args.multites_provenance)


if __name__ == "__main__":
    main()
