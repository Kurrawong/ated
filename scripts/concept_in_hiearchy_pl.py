#!/usr/bin/env python3

import argparse
import sys
from collections import defaultdict

from kurra.sparql import query


SPARQL = """
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT
    ?concept
    ?direction
    (COUNT(DISTINCT ?mid) AS ?distance)
    (SAMPLE(STR(?label)) AS ?prefLabel)
WHERE {{
    VALUES ?givenConcept {{ <{concept_iri}> }}

    {{
        ?givenConcept
            (skos:broader | ^skos:narrower)*
            ?mid .

        ?mid
            (skos:broader | ^skos:narrower)+
            ?concept .

        BIND("broader" AS ?direction)
    }}
    UNION
    {{
        ?givenConcept
            (skos:narrower | ^skos:broader)*
            ?mid .

        ?mid
            (skos:narrower | ^skos:broader)+
            ?concept .

        BIND("narrower" AS ?direction)
    }}

    OPTIONAL {{
        ?concept skos:prefLabel ?label .
    }}

    FILTER(?concept != ?givenConcept)
}}
GROUP BY ?concept ?direction
ORDER BY ?direction ?distance ?concept
"""


LABEL_QUERY = """
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT (SAMPLE(STR(?label)) AS ?prefLabel)
WHERE {{
    OPTIONAL {{
        <{concept_iri}> skos:prefLabel ?label .
    }}
}}
"""


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Display the broader and narrower concepts as a tree."
    )
    parser.add_argument("endpoint_url", help="SPARQL endpoint URL")
    parser.add_argument("concept_iri", help="Target SKOS Concept IRI")
    return parser.parse_args()


def validate_iri(iri):
    """Reject characters that could break out of a SPARQL IRI reference."""
    forbidden = set('<>"{}|\\^`')

    if (
        not iri
        or ":" not in iri
        or any(character.isspace() for character in iri)
        or any(character in forbidden for character in iri)
    ):
        raise ValueError(f"Invalid IRI: {iri}")

    return iri


def retrieve_results(endpoint_url, concept_iri):
    concept_iri = validate_iri(concept_iri)

    hierarchy_bindings = query(
        endpoint_url,
        SPARQL.format(concept_iri=concept_iri),
        return_format="python",
        return_bindings_only=True,
    )

    label_bindings = query(
        endpoint_url,
        LABEL_QUERY.format(concept_iri=concept_iri),
        return_format="python",
        return_bindings_only=True,
    )

    target_label = concept_iri

    if label_bindings and label_bindings[0].get("prefLabel"):
        target_label = str(label_bindings[0]["prefLabel"])

    return hierarchy_bindings, target_label


def group_results(bindings):
    grouped = defaultdict(lambda: defaultdict(list))

    for binding in bindings:
        try:
            concept_iri = str(binding["concept"])
            direction = str(binding["direction"])
            distance = int(binding["distance"])
            label = str(binding.get("prefLabel") or concept_iri)
        except (KeyError, TypeError, ValueError) as error:
            print(
                f"Warning: skipping invalid result {binding!r}: {error}",
                file=sys.stderr,
            )
            continue

        # Keep the IRI internally so concepts sharing a label remain distinct.
        grouped[direction][distance].append((label, concept_iri))

    return grouped


def print_tree(target_label, grouped):
    broader = grouped.get("broader", {})
    narrower = grouped.get("narrower", {})

    maximum_broader_distance = max(broader, default=0)

    # Print broader levels from most distant to closest.
    for distance in sorted(broader, reverse=True):
        concepts = sorted(
            broader[distance],
            key=lambda item: (item[0].casefold(), item[1]),
        )
        indent = "    " * (maximum_broader_distance - distance)

        for number, (label, _iri) in enumerate(concepts):
            connector = "└── " if number == len(concepts) - 1 else "├── "
            print(
                f"{indent}{connector}"
                #f"{label} [broader, distance {distance}]"
                f"{label}"
            )

    root_indent = "    " * maximum_broader_distance

    if broader:
        print(f"{root_indent}└── {target_label} [given concept]")
    else:
        print(f"{target_label} [given concept]")

    # Print narrower levels below the given concept.
    for distance in sorted(narrower):
        concepts = sorted(
            narrower[distance],
            key=lambda item: (item[0].casefold(), item[1]),
        )
        indent = "    " * (maximum_broader_distance + distance)

        for number, (label, _iri) in enumerate(concepts):
            connector = "└── " if number == len(concepts) - 1 else "├── "
            print(
                f"{indent}{connector}"
                #f"{label} [narrower, distance {distance}]"
                f"{label}"
            )

    if not broader and not narrower:
        print("    └── no broader or narrower concepts found")


def main():
    args = parse_arguments()

    try:
        bindings, target_label = retrieve_results(
            args.endpoint_url,
            args.concept_iri,
        )
        grouped = group_results(bindings)
        print_tree(target_label, grouped)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())