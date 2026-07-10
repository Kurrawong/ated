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

    FILTER(?concept != ?givenConcept)
}}
GROUP BY ?concept ?direction
ORDER BY ?direction ?distance ?concept
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
    sparql = SPARQL.format(concept_iri=validate_iri(concept_iri))

    return query(
        endpoint_url,
        sparql,
        return_format="python",
        return_bindings_only=True,
    )


def group_results(bindings):
    grouped = defaultdict(lambda: defaultdict(set))

    for binding in bindings:
        try:
            concept = str(binding["concept"])
            direction = str(binding["direction"])
            distance = int(binding["distance"])
        except (KeyError, TypeError, ValueError) as error:
            print(
                f"Warning: skipping invalid result {binding!r}: {error}",
                file=sys.stderr,
            )
            continue

        grouped[direction][distance].add(concept)

    return grouped


def print_tree(concept_iri, grouped):
    broader = grouped.get("broader", {})
    narrower = grouped.get("narrower", {})

    maximum_broader_distance = max(broader, default=0)

    # Print broader levels from most distant to closest.
    for distance in sorted(broader, reverse=True):
        concepts = sorted(broader[distance])
        indent = "    " * (maximum_broader_distance - distance)

        for number, concept in enumerate(concepts):
            is_last = number == len(concepts) - 1
            connector = "└── " if is_last else "├── "
            print(
                f"{indent}{connector}"
                #f"{concept} [broader, distance {distance}]"
                f"{concept}"
            )

    # Place the given concept below all broader levels.
    root_indent = "    " * maximum_broader_distance

    if broader:
        print(f"{root_indent}└── {concept_iri} [given concept]")
    else:
        print(f"{concept_iri} [given concept]")

    # Print narrower levels below the given concept.
    for distance in sorted(narrower):
        concepts = sorted(narrower[distance])
        indent = "    " * (maximum_broader_distance + distance)

        for number, concept in enumerate(concepts):
            is_last = number == len(concepts) - 1
            connector = "└── " if is_last else "├── "
            print(
                f"{indent}{connector}"
                f"{concept}"
                #f"{concept} [narrower, distance {distance}]"
            )

    if not broader and not narrower:
        print("    └── no broader or narrower concepts found")


def main():
    args = parse_arguments()

    try:
        bindings = retrieve_results(
            args.endpoint_url,
            args.concept_iri,
        )
        grouped = group_results(bindings)
        print_tree(args.concept_iri, grouped)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())