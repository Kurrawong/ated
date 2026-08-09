#!/usr/bin/env python3
"""Compatibility wrapper for the YAML-driven subject-category transformation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ated_transform.build import build_subject_categories_graph, write_graph
from ated_transform.config import load_mapping


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    mapping = load_mapping(ROOT / "mappings/ated-subject-categories.yaml")
    write_graph(build_subject_categories_graph(args.source, mapping), args.destination)


if __name__ == "__main__":
    main()
