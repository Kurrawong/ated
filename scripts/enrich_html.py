#!/usr/bin/env python3
"""Add ATED-specific metadata rows to pyLODE-generated HTML.

pyLODE's VocPub renderer does not currently render every SKOS-plus predicate used
by ATED. This post-processes the generated HTML so concept pages include:

* dcterms:subject, linked to the ATED Subject Categories HTML page
* dcterms:modified, preserving xsd:gYear / xsd:gYearMonth lexical values
"""

from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass, field
from pathlib import Path


ATED_BASE = "https://linked.data.gov.au/def/ated/"
DCTERMS_SUBJECT = "http://purl.org/dc/terms/subject"
DCTERMS_MODIFIED = "http://purl.org/dc/terms/modified"


@dataclass
class ConceptMetadata:
    subjects: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)


def parse_subject_category_labels(path: Path) -> dict[str, str]:
    """Return subject category IDs mapped to their English prefLabels."""
    labels: dict[str, str] = {}
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        subject_match = re.match(r"(?:atedsc:|:)(\d{3})\n", block)
        if not subject_match:
            continue
        label_match = re.search(r'skos:prefLabel\s+"([^"]+)"@en', block)
        if label_match:
            labels[subject_match.group(1)] = label_match.group(1)
    return labels


def turtle_literal_to_text(value: str) -> str:
    """Unescape the small Turtle literal subset used in this repository."""
    return (
        value.replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\\\", "\\")
    )


def parse_scheme_definition(path: Path) -> str | None:
    """Return the cs: skos:definition value from an ATED Turtle file."""
    text = path.read_text(encoding="utf-8")
    scheme_match = re.search(r"^cs:\n(?P<body>.*?)(?:\n\.)", text, flags=re.DOTALL | re.MULTILINE)
    if not scheme_match:
        return None

    body = scheme_match.group("body")
    definition_match = re.search(
        r'skos:definition\s+"""(?P<triple>.*?)"""@en',
        body,
        flags=re.DOTALL,
    )
    if definition_match:
        return definition_match.group("triple")

    definition_match = re.search(r'skos:definition\s+"(?P<single>(?:\\"|[^"])*)"@en', body)
    if definition_match:
        return turtle_literal_to_text(definition_match.group("single"))

    return None


def parse_concept_metadata(path: Path) -> dict[str, ConceptMetadata]:
    """Return local concept names mapped to ATED-specific HTML metadata."""
    concepts: dict[str, ConceptMetadata] = {}
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        subject_match = re.match(r":([A-Za-z][A-Za-z0-9]*)\n", block)
        if not subject_match or "a skos:Concept" not in block:
            continue

        local_name = subject_match.group(1)
        metadata = ConceptMetadata()
        metadata.subjects = re.findall(r"dcterms:subject\s+atedsc:(\d{3})", block)
        metadata.modified = re.findall(
            r'dcterms:modified\s+"([^"]+)"\^\^xsd:gYear(?:Month)?',
            block,
        )
        if metadata.subjects or metadata.modified:
            concepts[local_name] = metadata
    return concepts


def html_paragraphs(value: str) -> str:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", value) if paragraph.strip()]
    return "\n".join(f"                <p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)


def enrich_scheme_definition(html_text: str, definition: str | None) -> str:
    """Replace the rendered ConceptScheme definition with the TTL value."""
    if not definition:
        return html_text

    definition_pattern = re.compile(
        r'(?P<block><div>\n'
        r'\s*<dt>\n'
        r'\s*<a href="http://www\.w3\.org/2004/02/skos/core#definition">Definition</a>\n'
        r'\s*</dt>\n'
        r'\s*<dd>\n'
        r'\s*<div>\n)'
        r'.*?'
        r'(?P<tail>\n\s*</div>\n\s*</dd>\n\s*</div>)',
        flags=re.DOTALL,
    )
    return definition_pattern.sub(
        lambda match: match.group("block") + html_paragraphs(definition) + match.group("tail"),
        html_text,
        count=1,
    )


def subject_row(category_ids: list[str], category_labels: dict[str, str]) -> str:
    links = []
    for category_id in category_ids:
        label = category_labels.get(category_id, category_id)
        links.append(
            f'<a href="ated-sc.html#{category_id}">{html.escape(label)}</a>'
        )
    return (
        "            <tr>\n"
        "              <td>\n"
        f'                <a href="{DCTERMS_SUBJECT}" title="A topic of the resource.">Subject</a>\n'
        "              </td>\n"
        "              <td>\n"
        f"                {', '.join(links)}\n"
        "              </td>\n"
        "            </tr>\n"
    )


def modified_row(values: list[str]) -> str:
    escaped_values = ", ".join(html.escape(value) for value in values)
    return (
        "            <tr>\n"
        "              <td>\n"
        f'                <a href="{DCTERMS_MODIFIED}" title="Date on which the resource was changed.">Modified</a>\n'
        "              </td>\n"
        f"              <td>{escaped_values}</td>\n"
        "            </tr>\n"
    )


def enrich_html(
    html_text: str,
    concepts: dict[str, ConceptMetadata],
    category_labels: dict[str, str],
    scheme_definition: str | None = None,
) -> str:
    """Insert Subject and Modified rows into each matching concept table."""
    html_text = enrich_scheme_definition(html_text, scheme_definition)

    def replace_entity(match: re.Match[str]) -> str:
        local_name = match.group("id")
        entity = match.group(0)
        metadata = concepts.get(local_name)
        if not metadata:
            return entity

        rows = ""
        if metadata.subjects:
            rows += subject_row(metadata.subjects, category_labels)
        if metadata.modified:
            rows += modified_row(metadata.modified)
        if not rows:
            return entity

        # Make the script idempotent when re-run over already-enriched HTML.
        entity = re.sub(
            r"\n\s*<tr>\n\s*<td>\n\s*"
            rf'<a href="{re.escape(DCTERMS_SUBJECT)}".*?</tr>',
            "",
            entity,
            flags=re.DOTALL,
        )
        entity = re.sub(
            r"\n\s*<tr>\n\s*<td>\n\s*"
            rf'<a href="{re.escape(DCTERMS_MODIFIED)}".*?</tr>',
            "",
            entity,
            flags=re.DOTALL,
        )
        return entity.replace("          </table>", rows + "          </table>", 1)

    entity_pattern = re.compile(
        r'(?P<entity><div class="entity">\n'
        r'\s*<h3 id="(?P<id>[^"]+)">.*?</h3>\n'
        r'.*?\n\s*</table>\n'
        r'\s*</div>)',
        re.DOTALL,
    )
    return entity_pattern.sub(replace_entity, html_text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ated-ttl",
        type=Path,
        default=Path("vocabs/ated.ttl"),
        help="ATED Turtle source file.",
    )
    parser.add_argument(
        "--ated-sc-ttl",
        type=Path,
        default=Path("vocabs/ated-sc.ttl"),
        help="ATED Subject Categories Turtle source file.",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("vocabs/ated.html"),
        help="pyLODE-generated ATED HTML file to update in place.",
    )
    args = parser.parse_args()

    category_labels = parse_subject_category_labels(args.ated_sc_ttl)
    concepts = parse_concept_metadata(args.ated_ttl)
    scheme_definition = parse_scheme_definition(args.ated_ttl)
    enriched = enrich_html(
        args.html.read_text(encoding="utf-8"),
        concepts,
        category_labels,
        scheme_definition,
    )
    args.html.write_text(enriched, encoding="utf-8")


if __name__ == "__main__":
    main()
