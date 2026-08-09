"""Build ATED RDF graphs from source XML and declarative mappings."""

from __future__ import annotations

from pathlib import Path
from rdflib import DCTERMS, RDF, RDFS, SKOS, XSD, Graph, Literal, Namespace, URIRef

from .config import project_path
from .extract import descriptor_index, subject_categories, xml_root
from .normalise import amendment_date, source_text, subject_category_iri


SCHEMA = Namespace("https://schema.org/")
ATEDSC = Namespace("https://linked.data.gov.au/def/ated/SC/")

NAMESPACES = {
    "dcterms": DCTERMS,
    "rdf": RDF,
    "rdfs": RDFS,
    "schema": SCHEMA,
    "skos": SKOS,
    "xsd": XSD,
}


def bind_namespaces(graph: Graph, concept_namespace: str, scheme_iri: str) -> None:
    graph.bind("", Namespace(concept_namespace), replace=True)
    graph.bind("cs", Namespace(scheme_iri), replace=True)
    graph.bind("atedsc", ATEDSC, replace=True)
    for prefix, namespace in NAMESPACES.items():
        graph.bind(prefix, namespace, replace=True)


def expand_curie(value: str) -> URIRef:
    prefix, separator, local = value.partition(":")
    if not separator or prefix not in NAMESPACES:
        raise ValueError(f"Unsupported CURIE in mapping: {value!r}")
    return NAMESPACES[prefix][local]


def metadata_graph(mapping: dict) -> Graph:
    graph = Graph()
    graph.parse(project_path(mapping, mapping["output"]["metadata"]), format="turtle")
    return graph


def build_ated_graph(source: Path, mapping: dict) -> Graph:
    root = xml_root(source)
    index = descriptor_index(root, mapping["source"])
    output = mapping["output"]
    concept = mapping["concept"]
    language = output["language"]
    scheme = URIRef(output["scheme_iri"])
    iri_template = output["concept_iri_template"]
    category_template = "https://linked.data.gov.au/def/ated/SC/{identifier}"

    graph = metadata_graph(mapping)
    bind_namespaces(graph, iri_template.replace("{TNR}", ""), str(scheme))

    def concept_iri(label: str) -> URIRef:
        try:
            return URIRef(iri_template.format(TNR=index.tnrs[label]))
        except KeyError as error:
            raise ValueError(f"Unknown descriptor reference: {label!r}") from error

    for label, record in index.records.items():
        tnr = index.tnrs[label]
        subject = concept_iri(label)
        graph.add((subject, RDF.type, SKOS.Concept))
        graph.add((subject, RDFS.isDefinedBy, scheme))
        graph.add((subject, SKOS.inScheme, scheme))
        graph.add((subject, SKOS.prefLabel, Literal(source_text(label), lang=language)))
        graph.add(
            (
                subject,
                SKOS.definition,
                Literal(concept["definition_template"].format(DESCRIPTOR=label), lang=language),
            )
        )
        graph.add((subject, SKOS.notation, Literal(tnr, datatype=XSD.token)))
        graph.add(
            (
                subject,
                DCTERMS.source,
                URIRef(concept["source_iri_template"].format(TNR=tnr)),
            )
        )

        alt_labels = [e.text for e in record.findall("UF") if e.text]
        alt_labels.extend(index.non_descriptor_labels.get(label, ()))
        for alt_label in dict.fromkeys(alt_labels):
            graph.add(
                (subject, SKOS.altLabel, Literal(source_text(alt_label), lang=language))
            )

        for field_name, field in mapping["fields"].items():
            if field_name in {"DESCRIPTOR", "TNR", "UF"}:
                continue
            predicate = expand_curie(field["property"])
            for element in record.findall(field_name):
                if not element.text:
                    continue
                value = element.text
                value_type = field["value"]
                if value_type == "language_literal":
                    obj = Literal(source_text(value), lang=language)
                elif value_type == "descriptor_reference":
                    obj = concept_iri(source_text(value))
                elif value_type == "subject_category_iri":
                    obj = subject_category_iri(value, category_template)
                elif value_type == "amendment_date":
                    obj = amendment_date(value)
                else:
                    raise ValueError(f"Unsupported mapped value type: {value_type!r}")
                graph.add((subject, predicate, obj))

        if not record.findall("BT"):
            graph.add((subject, SKOS.topConceptOf, scheme))
            graph.add((scheme, SKOS.hasTopConcept, subject))

    return graph


def build_subject_categories_graph(source: Path, mapping: dict) -> Graph:
    root = xml_root(source)
    categories = subject_categories(root, mapping["source"])
    output = mapping["output"]
    concept = mapping["concept"]
    language = output["language"]
    scheme = URIRef(output["scheme_iri"])
    iri_template = output["concept_iri_template"]

    graph = metadata_graph(mapping)
    bind_namespaces(graph, iri_template.replace("{identifier}", ""), str(scheme))
    for identifier, label in sorted(categories.items(), key=lambda item: int(item[0])):
        subject = URIRef(iri_template.format(identifier=identifier))
        graph.add((subject, RDF.type, SKOS.Concept))
        graph.add((subject, RDFS.isDefinedBy, scheme))
        graph.add((subject, SKOS.inScheme, scheme))
        graph.add((subject, SKOS.topConceptOf, scheme))
        graph.add((scheme, SKOS.hasTopConcept, subject))
        graph.add((subject, SKOS.prefLabel, Literal(label, lang=language)))
        definition = concept["definition_template"].format(
            identifier=identifier,
            label=label,
            lower_label=label.lower(),
        )
        graph.add((subject, SKOS.definition, Literal(definition, lang=language)))
    return graph


def write_graph(graph: Graph, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=destination, format="longturtle", encoding="utf-8")


def graph_difference(left: Graph, right: Graph) -> tuple[set, set]:
    return set(left) - set(right), set(right) - set(left)


def concepts_without_subject(graph: Graph) -> set[URIRef]:
    return {
        subject
        for subject in graph.subjects(RDF.type, SKOS.Concept)
        if not any(graph.objects(subject, DCTERMS.subject))
    }
