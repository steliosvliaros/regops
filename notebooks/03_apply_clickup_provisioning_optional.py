from __future__ import annotations

import json
from pathlib import Path
from rich.console import Console

from regops.settings import get_settings
from regops.clickup.client import ClickUpClient
from regops.clickup.bootstrap import ensure_clickup_hierarchy, write_resolved_ids

console = Console()

ROOT = Path(__file__).resolve().parents[1]
PROVISION_PLAN_PATH = ROOT / "outputs" / "provision_plans" / "clickup_provision_plan.json"
RESOLVED_IDS_PATH = ROOT / "outputs" / "provision_plans" / "resolved_clickup_ids.json"


def _load_plan() -> dict:
    if not PROVISION_PLAN_PATH.exists():
        raise RuntimeError(
            f"Missing provision plan: {PROVISION_PLAN_PATH}\n"
            f"Run: python notebooks/02_generate_clickup_provision_plan.py"
        )
    return json.loads(PROVISION_PLAN_PATH.read_text(encoding="utf-8"))


def _field_options(field: dict) -> list[str]:
    type_config = field.get("type_config") or {}
    options = type_config.get("options") or []
    return [str(o.get("name")) for o in options if o.get("name")]


def _drift_check(client: ClickUpClient, list_id: str, plan: dict) -> None:
    # Check custom fields exist + dropdown option coverage
    fields_resp = client.get_list_fields(list_id)
    fields = fields_resp.get("fields", []) if isinstance(fields_resp, dict) else []
    by_name = {f.get("name"): f for f in fields if f.get("name")}

    missing_fields: list[str] = []
    dropdown_mismatches: list[tuple[str, str]] = []

    for pf in plan.get("custom_fields", []):
        name = pf.get("name")
        if not name:
            continue
        if name not in by_name:
            missing_fields.append(name)
            continue

        plan_opts = pf.get("options") or []
        if plan_opts:
            plan_opt_names: list[str] = []
            for o in plan_opts:
                if isinstance(o, str):
                    plan_opt_names.append(o)
                elif isinstance(o, dict) and o.get("name"):
                    plan_opt_names.append(str(o["name"]))

            cu_opts = set(_field_options(by_name[name]))
            for po in plan_opt_names:
                if po not in cu_opts:
                    dropdown_mismatches.append((name, po))

    # Check statuses exist (best-effort; depends on ClickUp response shape)
    status_missing: list[str] = []
    try:
        li = client.get_list(list_id)
        list_statuses = li.get("statuses") or []
        cu_status_names = set(str(s.get("status")) for s in list_statuses if s.get("status"))
        planned_statuses = plan.get("statuses", {}).get("global", [])
        for ps in planned_statuses:
            if ps not in cu_status_names:
                status_missing.append(ps)
    except Exception:
        pass

    if missing_fields:
        console.print("[yellow]⚠ Missing custom fields on the List:[/yellow]")
        for f in missing_fields:
            console.print(f"  - {f}")

    if dropdown_mismatches:
        console.print("[yellow]⚠ Dropdown option mismatches (field -> missing option):[/yellow]")
        for field_name, opt in dropdown_mismatches:
            console.print(f"  - {field_name} -> {opt}")

    if status_missing:
        console.print("[yellow]⚠ Missing statuses on the List (names):[/yellow]")
        for s in status_missing:
            console.print(f"  - {s}")

    if not (missing_fields or dropdown_mismatches or status_missing):
        console.print("[green]✅ Drift check passed: fields + options + statuses look aligned.[/green]")
    else:
        console.print(
            "[yellow]\nNOTE: ClickUp API cannot reliably create full status + custom field schemas.\n"
            "The supported approach is: create a TEMPLATE LIST once in the UI, then create new project lists FROM TEMPLATE.\n"
            "If you didn't provide CLICKUP_LIST_TEMPLATE_ID, you likely created a plain list (no schema carrier).\n[/yellow]"
        )


def main() -> None:
    s = get_settings()
    plan = _load_plan()

    if not s.clickup_api_token:
        raise RuntimeError("CLICKUP_API_TOKEN is required.")

    client = ClickUpClient(base_url=s.clickup_base_url, token=s.clickup_api_token, dry_run=s.dry_run)

    # Require names for name-first provisioning
    if not s.clickup_space_name or not s.clickup_folder_name or not s.clickup_project_list_name:
        raise RuntimeError(
            "Set these in .env for name-first provisioning:\n"
            "  CLICKUP_SPACE_NAME\n"
            "  CLICKUP_FOLDER_NAME\n"
            "  CLICKUP_PROJECT_LIST_NAME\n"
            "(Optionally CLICKUP_WORKSPACE_NAME if you have multiple workspaces.)"
        )

    resolved = ensure_clickup_hierarchy(
        client,
        team_id=s.clickup_team_id,
        workspace_name=s.clickup_workspace_name,
        space_name=s.clickup_space_name,
        folder_name=s.clickup_folder_name,
        list_name=s.clickup_project_list_name,
        template_id=s.clickup_list_template_id,
    )

    write_resolved_ids(RESOLVED_IDS_PATH, resolved)

    console.print("[bold]Resolved ClickUp IDs[/bold]")
    console.print(f"  workspace/team_id: {resolved.team_id} ({resolved.workspace_name})")
    console.print(f"  space_id:         {resolved.space_id} ({resolved.space_name})")
    console.print(f"  folder_id:        {resolved.folder_id} ({resolved.folder_name})")
    console.print(f"  list_id:          {resolved.list_id} ({resolved.list_name})")
    console.print(f"  template_id:      {resolved.template_id}")
    console.print(f"Wrote: {RESOLVED_IDS_PATH}")

    _drift_check(client, resolved.list_id, plan)


if __name__ == "__main__":
    main()
