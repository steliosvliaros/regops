from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass(frozen=True)
class ClickUpFieldSpec:
    name: str
    type: str
    options: List[str]
    required: bool
    maps_from_library_field: str


def load_clickup_field_map(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def field_specs(map_yaml: Dict[str, Any]) -> List[ClickUpFieldSpec]:
    specs: List[ClickUpFieldSpec] = []
    for cf in map_yaml.get("custom_fields", []):
        specs.append(ClickUpFieldSpec(
            name=cf["name"],
            type=cf["type"],
            options=cf.get("options", []) or [],
            required=bool(cf.get("required", False)),
            maps_from_library_field=str(cf.get("maps_from_library_field", "")),
        ))
    return specs
