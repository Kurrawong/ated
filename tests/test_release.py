from __future__ import annotations

import sys
import unittest
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ated_transform.build import (
    build_ated_graph,
    build_subject_categories_graph,
    concepts_without_subject,
)
from ated_transform.config import load_mapping


SOURCE = ROOT / "raw/xml/ATED June2026 with TNRs.xml"


@unittest.skipUnless(SOURCE.exists(), "raw MultiTes export is not available")
class ReleaseRegressionTests(unittest.TestCase):
    def assert_graph_equal(self, generated: Graph, published_path: Path):
        published = Graph().parse(published_path, format="turtle")
        self.assertEqual(
            set(generated),
            set(published),
            f"generated graph differs from {published_path}",
        )

    def test_ated_release_graph(self):
        mapping = load_mapping(ROOT / "mappings/ated.yaml")
        graph = build_ated_graph(SOURCE, mapping)
        self.assert_graph_equal(graph, ROOT / "vocabs/ated.ttl")
        self.assertEqual(
            len(concepts_without_subject(graph)),
            mapping["validation"]["known_warnings"]["missing_subject_category"],
        )

    def test_subject_category_release_graph(self):
        graph = build_subject_categories_graph(
            SOURCE, load_mapping(ROOT / "mappings/ated-subject-categories.yaml")
        )
        self.assert_graph_equal(graph, ROOT / "vocabs/ated-sc.ttl")
