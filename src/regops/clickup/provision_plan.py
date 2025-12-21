from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def generate_provision_plan(field_map: Dict[str, Any]) -> Dict[str, Any]:
    statuses = field_map.get("statuses", {})
    custom_fields = field_map.get("custom_fields", [])
    plan = {
        "generated_from": "regops_library/clickup/clickup_field_map.yaml",
        "recommended_hierarchy": {
            "space": "RegOps — Projects",
            "folders": [
                {"name": "01 — Active Projects", "lists": ["<one list per project instance>"]},
                {"name": "99 — Templates", "lists": ["Template Library List (optional)"]},
            ],
        },
        "statuses": statuses,
        "custom_fields": custom_fields,
        "template_strategy": field_map.get("template_strategy", {}),
        "sync_policy": field_map.get("sync_policy", []),
        "manual_steps": [
            "Create/confirm the Space/Folder/List scaffolding in ClickUp (if not already present).",
            "Create custom fields (by name/type/options) in the target List (or as List template).",
            "Create/confirm statuses (if API cannot create custom statuses, create them manually).",
            "Record IDs in .env (SPACE_ID/FOLDER_ID/TARGET_LIST_ID as needed).",
        ],
    }
    return plan
