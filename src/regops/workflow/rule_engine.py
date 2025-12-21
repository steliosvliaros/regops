from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set


@dataclass(frozen=True)
class ProjectProfile:
    project_id: str
    project_name: str
    plan_start_date: str  # ISO date
    classification: str
    environmental_regime: str
    project_type: str
    grid_interaction: str
    capacity_band: str
    regulatory_path: str
    location_constraint: str
    meta: Dict[str, Any] | None = None


def _match_dim(value: str, allowed_values: List[str]) -> bool:
    if "ANY" in allowed_values:
        return True
    return value in allowed_values


def evaluate_applicability(rules: List[Dict[str, Any]], profile: ProjectProfile) -> Dict[str, Any]:
    included: Set[str] = set()
    excluded: Set[str] = set()
    matched_rules: List[str] = []

    for rule in rules:
        rid = rule.get("rule_id", "UNKNOWN")
        m = rule.get("match", {})
        ok = True
        ok &= _match_dim(profile.classification, m.get("classification", ["ANY"]))
        ok &= _match_dim(profile.project_type, m.get("project_type", ["ANY"]))
        ok &= _match_dim(profile.grid_interaction, m.get("grid_interaction", ["ANY"]))
        ok &= _match_dim(profile.capacity_band, m.get("capacity_band", ["ANY"]))
        ok &= _match_dim(profile.regulatory_path, m.get("regulatory_path", ["ANY"]))
        ok &= _match_dim(profile.location_constraint, m.get("location_constraint", ["ANY"]))
        ok &= _match_dim(profile.environmental_regime, m.get("environmental_regime", ["ANY"]))

        if ok:
            matched_rules.append(rid)
            a = rule.get("apply", {})
            included.update(a.get("include_tasks", []) or [])
            excluded.update(a.get("exclude_tasks", []) or [])

    final_tasks = sorted(list(included - excluded))
    return {
        "matched_rules": matched_rules,
        "include": sorted(list(included)),
        "exclude": sorted(list(excluded)),
        "final_tasks": final_tasks,
    }
