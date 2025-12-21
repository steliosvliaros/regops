from __future__ import annotations

from typing import Any, Dict, List

from regops.clickup.client import ClickUpClient


def best_effort_provision(client: ClickUpClient, plan: Dict[str, Any], space_id: str, folder_id: str, target_list_id: str) -> Dict[str, Any]:
    """Best-effort provisioning.
    ClickUp API support for creating statuses/custom fields is limited; therefore this primarily:
    - validates access to space/folder/list,
    - fetches existing list custom fields (for name matching),
    and returns a checklist for manual actions.
    """
    out: Dict[str, Any] = {"checks": {}, "manual_steps": plan.get("manual_steps", [])}

    # Verify access
    if space_id:
        out["checks"]["folders"] = client.get_folders(space_id)

    if folder_id:
        out["checks"]["folder_lists"] = client.get_folder_lists(folder_id)

    if target_list_id:
        out["checks"]["list_fields"] = client.get_list_fields(target_list_id)

    # Recommend: compare existing fields by name
    existing_fields = {f.get("name"): f for f in out.get("checks", {}).get("list_fields", {}).get("fields", [])} if isinstance(out.get("checks", {}).get("list_fields"), dict) else {}
    needed = plan.get("custom_fields", [])
    missing = [cf for cf in needed if cf.get("name") not in existing_fields]
    out["missing_custom_fields"] = missing

    return out
