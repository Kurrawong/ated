#!/usr/bin/env python3
"""Convert the ATED XML export to SKOS Turtle."""

from __future__ import annotations

import argparse
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


BASE_IRI = "https://linked.data.gov.au/def/ated/"
SCHEME_IRI = "https://linked.data.gov.au/def/ated"


def local_name(label: str) -> str:
    """Convert a descriptor to a lower-camel-case IRI suffix."""
    normalized = unicodedata.normalize("NFKD", label)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    if not words:
        raise ValueError(f"Cannot generate an IRI suffix from {label!r}")
    return words[0].lower() + "".join(
        word[:1].upper() + word[1:].lower() for word in words[1:]
    )


def turtle_string(value: str, language: str | None = None) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    literal = f'"{escaped}"'
    return f"{literal}@{language}" if language else literal


def iri_for(label: str) -> str:
    return f"<{BASE_IRI}{local_name(label)}>"


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


def convert(source: Path, destination: Path) -> None:
    root = ET.parse(source).getroot()
    records = root.findall("CONCEPT")
    descriptors = {
        record.findtext("DESCRIPTOR"): record
        for record in records
        if record.find("DESCRIPTOR") is not None
    }

    suffixes: dict[str, list[str]] = defaultdict(list)
    for descriptor in descriptors:
        suffixes[local_name(descriptor)].append(descriptor)
    collisions = {
        suffix: labels for suffix, labels in suffixes.items() if len(labels) > 1
    }
    if collisions:
        details = "; ".join(
            f"{suffix}: {labels}" for suffix, labels in sorted(collisions.items())
        )
        raise ValueError(f"Generated IRI collisions: {details}")

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

    blocks = [
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
        render_subject(
            "<https://linked.data.gov.au/def/ated>",
            [
                ("a", ["skos:ConceptScheme"]),
                ("skos:prefLabel", [turtle_string("Australian Thesaurus of Education Descriptors", "en")]),
            ],
        ),
    ]

    for descriptor, record in descriptors.items():
        statements: list[tuple[str, list[str]]] = [
            ("a", ["skos:Concept"]),
            ("skos:inScheme", [f"<{SCHEME_IRI}>"]),
            ("skos:prefLabel", [turtle_string(descriptor, "en")]),
        ]

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
            [iri_for(element.text) for element in record.findall("BT")],
        )
        add_statement(
            statements,
            "skos:narrower",
            [iri_for(element.text) for element in record.findall("NT")],
        )
        add_statement(
            statements,
            "skos:related",
            [iri_for(element.text) for element in record.findall("RT")],
        )
        add_statement(
            statements,
            "dcterms:subject",
            [turtle_string(element.text, "en") for element in record.findall("SC")],
        )
        add_statement(
            statements,
            "dcterms:modified",
            [turtle_string(element.text) for element in record.findall("AD")],
        )
        if not record.findall("BT"):
            statements.insert(2, ("skos:topConceptOf", [f"<{SCHEME_IRI}>"]))

        blocks.append(render_subject(iri_for(descriptor), statements))

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination)


if __name__ == "__main__":
    main()
