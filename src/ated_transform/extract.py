"""Extract source records and indexes from a MultiTes XML export."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DescriptorIndex:
    records: dict[str, ET.Element]
    tnrs: dict[str, str]
    non_descriptor_labels: dict[str, tuple[str, ...]]


def xml_root(source: Path) -> ET.Element:
    return ET.parse(source).getroot()


def descriptor_index(root: ET.Element, source_config: dict) -> DescriptorIndex:
    records = root.findall(source_config["record_xpath"])
    descriptor_element = source_config["descriptor_element"]
    non_descriptor_element = source_config["non_descriptor_element"]
    use_element = source_config["use_element"]

    descriptors: dict[str, ET.Element] = {}
    for record in records:
        label = record.findtext(descriptor_element)
        if label is None:
            continue
        if label in descriptors:
            raise ValueError(f"Duplicate descriptor label: {label!r}")
        descriptors[label] = record

    tnrs: dict[str, str] = {}
    tnr_labels: dict[str, list[str]] = defaultdict(list)
    for label, record in descriptors.items():
        values = [e.text.strip() for e in record.findall("TNR") if e.text and e.text.strip()]
        if len(values) != 1:
            raise ValueError(f"Descriptor {label!r} must have exactly one TNR; found {values}")
        tnrs[label] = values[0]
        tnr_labels[values[0]].append(label)
    duplicates = {tnr: labels for tnr, labels in tnr_labels.items() if len(labels) > 1}
    if duplicates:
        raise ValueError(f"Duplicate descriptor TNRs: {duplicates}")

    alternative_labels: dict[str, list[str]] = defaultdict(list)
    for record in records:
        label = record.findtext(non_descriptor_element)
        if not label:
            continue
        uses = [e.text for e in record.findall(use_element) if e.text]
        if not uses:
            raise ValueError(f"Non-descriptor {label!r} has no USE target")
        for preferred in uses:
            if preferred not in descriptors:
                raise ValueError(
                    f"Non-descriptor {label!r} refers to unknown descriptor {preferred!r}"
                )
            alternative_labels[preferred].append(label)

    return DescriptorIndex(
        records=descriptors,
        tnrs=tnrs,
        non_descriptor_labels={
            label: tuple(dict.fromkeys(values))
            for label, values in alternative_labels.items()
        },
    )


def subject_categories(root: ET.Element, source_config: dict) -> dict[str, str]:
    pattern = re.compile(source_config["category_pattern"])
    categories: dict[str, str] = {}
    for element in root.iter(source_config["category_element"]):
        if not element.text:
            continue
        match = pattern.fullmatch(element.text.strip())
        if not match:
            raise ValueError(f"Unrecognised subject category: {element.text!r}")
        identifier = match.group("identifier")
        label = match.group("label")
        existing = categories.get(identifier)
        if existing is not None and existing != label:
            raise ValueError(
                f"Subject category {identifier} has conflicting labels: "
                f"{existing!r} and {label!r}"
            )
        categories[identifier] = label
    if not categories:
        raise ValueError("No subject categories found")
    return categories
