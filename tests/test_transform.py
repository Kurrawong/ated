from __future__ import annotations

import sys
import unittest
from pathlib import Path

from rdflib import DCTERMS, RDF, SKOS, XSD, Literal, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ated_transform.build import build_ated_graph, build_subject_categories_graph
from ated_transform.config import load_mapping
from ated_transform.normalise import amendment_date, source_text


FIXTURE = ROOT / "tests/fixtures/minimal-multites.xml"
ATED_MAPPING = ROOT / "mappings/ated.yaml"
SC_MAPPING = ROOT / "mappings/ated-subject-categories.yaml"


class AmendmentDateTests(unittest.TestCase):
    def test_month_and_two_digit_year(self):
        self.assertEqual(
            amendment_date("Jan 84"), Literal("1984-01", datatype=XSD.gYearMonth)
        )

    def test_four_digit_year_preserves_year_precision(self):
        self.assertEqual(amendment_date("2015"), Literal("2015", datatype=XSD.gYear))

    def test_unrecognised_date_fails(self):
        with self.assertRaisesRegex(ValueError, "Unrecognised amendment date"):
            amendment_date("sometime in 2015")

    def test_trailing_xml_whitespace_is_removed_but_line_breaks_remain(self):
        self.assertEqual(
            source_text("First line \nsecond line  \n third line"),
            "First line\nsecond line\n third line",
        )


class AtedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = build_ated_graph(FIXTURE, load_mapping(ATED_MAPPING))

    def test_only_descriptors_become_concepts(self):
        concepts = set(self.graph.subjects(RDF.type, SKOS.Concept))
        self.assertEqual(
            concepts,
            {
                URIRef("https://linked.data.gov.au/def/ated/100"),
                URIRef("https://linked.data.gov.au/def/ated/101"),
                URIRef("https://linked.data.gov.au/def/ated/102"),
            },
        )

    def test_non_descriptor_use_becomes_alternative_label(self):
        teaching = URIRef("https://linked.data.gov.au/def/ated/101")
        self.assertIn((teaching, SKOS.altLabel, Literal("Pedagogy", lang="en")), self.graph)
        self.assertNotIn(
            (URIRef("https://linked.data.gov.au/def/ated/999"), RDF.type, SKOS.Concept),
            self.graph,
        )

    def test_references_resolve_to_tnr_iris(self):
        teaching = URIRef("https://linked.data.gov.au/def/ated/101")
        education = URIRef("https://linked.data.gov.au/def/ated/100")
        self.assertIn((teaching, SKOS.broader, education), self.graph)

    def test_tnr_is_typed_notation_and_source_identifier(self):
        teaching = URIRef("https://linked.data.gov.au/def/ated/101")
        self.assertIn((teaching, SKOS.notation, Literal("101", datatype=XSD.token)), self.graph)
        sources = list(self.graph.objects(teaching, DCTERMS.source))
        self.assertEqual(len(sources), 1)
        self.assertIn("w=101", str(sources[0]))

    def test_top_concepts_are_derived_from_absence_of_bt(self):
        scheme = URIRef("https://linked.data.gov.au/def/ated")
        education = URIRef("https://linked.data.gov.au/def/ated/100")
        teaching = URIRef("https://linked.data.gov.au/def/ated/101")
        self.assertIn((education, SKOS.topConceptOf, scheme), self.graph)
        self.assertNotIn((teaching, SKOS.topConceptOf, scheme), self.graph)


class SubjectCategoryGraphTests(unittest.TestCase):
    def test_categories_are_deduplicated_and_top_concepts(self):
        graph = build_subject_categories_graph(FIXTURE, load_mapping(SC_MAPPING))
        concepts = set(graph.subjects(RDF.type, SKOS.Concept))
        self.assertEqual(len(concepts), 2)
        scheme = URIRef("https://linked.data.gov.au/def/ated/SC")
        category = URIRef("https://linked.data.gov.au/def/ated/SC/310")
        self.assertIn((category, SKOS.topConceptOf, scheme), graph)


if __name__ == "__main__":
    unittest.main()
