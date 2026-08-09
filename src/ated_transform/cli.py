"""Command-line interface for reproducible ATED RDF builds."""

from __future__ import annotations

import argparse
from pathlib import Path

from rdflib import Graph

from .build import (
    build_ated_graph,
    build_subject_categories_graph,
    concepts_without_subject,
    graph_difference,
    write_graph,
)
from .config import load_mapping


def compare_release(name: str, generated: Graph, release_path: Path) -> None:
    release = Graph().parse(release_path, format="turtle")
    only_generated, only_release = graph_difference(generated, release)
    if only_generated or only_release:
        raise SystemExit(
            f"{name} differs from {release_path}: "
            f"{len(only_generated)} generated-only and "
            f"{len(only_release)} release-only triples"
        )
    print(f"{name}: graph-equivalent to {release_path} ({len(generated)} triples)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="MultiTes XML export")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--mapping", type=Path, default=Path("mappings/ated.yaml"))
    parser.add_argument(
        "--subject-mapping",
        type=Path,
        default=Path("mappings/ated-subject-categories.yaml"),
    )
    parser.add_argument(
        "--check-release",
        action="store_true",
        help="fail unless generated graphs equal the checked-in vocabs graphs",
    )
    args = parser.parse_args()

    ated_mapping = load_mapping(args.mapping)
    subject_mapping = load_mapping(args.subject_mapping)
    ated = build_ated_graph(args.source, ated_mapping)
    subjects = build_subject_categories_graph(args.source, subject_mapping)

    ated_path = args.output_dir / "ated.ttl"
    subjects_path = args.output_dir / "ated-sc.ttl"
    write_graph(ated, ated_path)
    write_graph(subjects, subjects_path)
    print(f"Wrote {ated_path} ({len(ated)} triples)")
    print(f"Wrote {subjects_path} ({len(subjects)} triples)")

    expected_missing_subjects = ated_mapping.get("validation", {}).get(
        "known_warnings", {}
    ).get("missing_subject_category")
    missing_subjects = concepts_without_subject(ated)
    if (
        expected_missing_subjects is not None
        and len(missing_subjects) != expected_missing_subjects
    ):
        raise SystemExit(
            "Unexpected number of concepts without subject categories: "
            f"expected {expected_missing_subjects}, found {len(missing_subjects)}"
        )
    print(
        "Known warning — concepts without subject categories: "
        f"{len(missing_subjects)}"
    )

    if args.check_release:
        compare_release("ATED", ated, Path("vocabs/ated.ttl"))
        compare_release("ATED Subject Categories", subjects, Path("vocabs/ated-sc.ttl"))


if __name__ == "__main__":
    main()
