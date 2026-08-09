"""Named normalisation rules referenced by the YAML mappings."""

from __future__ import annotations

import re

from rdflib import Literal, URIRef
from rdflib.namespace import XSD


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


def source_text(value: str) -> str:
    """Remove trailing XML whitespace while retaining line breaks and leading text."""
    return "\n".join(line.rstrip() for line in value.splitlines()).strip()


def amendment_date(value: str) -> Literal:
    """Parse a MultiTes amendment date without inventing precision."""
    compact = re.sub(r"\s+", " ", value.strip())
    year_only = re.fullmatch(r"(\d{4})", compact)
    if year_only:
        return Literal(year_only.group(1), datatype=XSD.gYear)

    month_year = re.fullmatch(r"([A-Za-z]+)\s*(\d{2}|\d{4})", compact)
    if not month_year:
        raise ValueError(f"Unrecognised amendment date: {value!r}")
    month_name, year_text = month_year.groups()
    try:
        month = MONTHS[month_name.lower()]
    except KeyError as error:
        raise ValueError(f"Unrecognised month in amendment date: {value!r}") from error
    year = int(year_text)
    if len(year_text) == 2:
        year += 1900 if year >= 50 else 2000
    return Literal(f"{year:04d}-{month:02d}", datatype=XSD.gYearMonth)


def subject_category_iri(value: str, category_template: str) -> URIRef:
    match = re.fullmatch(r"(\d{3})\s+.+", value.strip())
    if not match:
        raise ValueError(f"Unrecognised subject category: {value!r}")
    return URIRef(category_template.format(identifier=match.group(1)))
