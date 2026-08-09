"""Load and validate the human-readable transformation contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        mapping = yaml.safe_load(stream)
    if not isinstance(mapping, dict):
        raise ValueError(f"Mapping must be a YAML object: {path}")
    if mapping.get("version") != 1:
        raise ValueError(f"Unsupported mapping version in {path}: {mapping.get('version')!r}")
    for key in ("source", "output", "concept"):
        if key not in mapping:
            raise ValueError(f"Mapping {path} is missing required section {key!r}")
    mapping["_path"] = path.resolve()
    mapping["_root"] = path.resolve().parent.parent
    return mapping


def project_path(mapping: dict[str, Any], configured_path: str) -> Path:
    return Path(mapping["_root"]) / configured_path
