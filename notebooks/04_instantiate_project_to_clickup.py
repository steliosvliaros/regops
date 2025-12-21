# notebooks/04_instantiate_project_to_clickup.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, time, date

import pandas as pd
import yaml
from rich.console import Console

from regops.settings import get_settings
from regops.io.load_library import load_library
from regops.workflow.rule_engine import ProjectProfile, evaluate_applicability
from regops.workflow.instantiate import compile_tasks
from regops.workflow.schedule import compute_schedule
from regops.clickup.client import ClickUpClient
from regops.reports.exports import write_csv, write_json

console = Console()
ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = ROOT / "regops_library"

# Change this to your real profile file
PROFILE_PATH = LIB_ROOT / "projects" / "project_profile_SCH001.yaml"


# -----------------------------
# Profile + time helpers
# -----------------------------
def load_profile(path: Path) -> ProjectProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ProjectProfile(
        project_id=data["project_id"],
        project_name=data.get("project_name", data["project_id"]),
        plan_start_date=data["plan_start_date"],
        classification=data["classification"],
        environmental_regime=data["environmental_regime"],
        project_type=data["project_type"],
        grid_interaction=data["grid_interaction"],
        capacity_band=data["capacity_band"],
        regulatory_path=data["regulatory_path"],
        location_constraint=data["location_constraint"],
        meta=data.get("meta"),
    )


def date_to_ms(d: date) -> int:
    """ClickUp expects ms epoch. Use local midnight; good enough for planning dates."""
    return int(datetime.combine(d, time.min).timestamp() * 1000)


# -----------------------------
# ClickUp custom field helpers
# -----------------------------
def fetch_all_tasks(client: ClickUpClient, list_id: str, include_closed: bool = True) -> List[Dict[str, Any]]:
    """Best-effort pagination until empty."""
    out: List[Dict[str, Any]] = []
    page = 0
    while True:
        data = client.get_tasks(list_id, include_closed=include_closed, page=page)
        batch = data.get("tasks", []) if isinstance(data, dict) else []
        if not batch:
            break
        out.extend(batch)
        page += 1
        if page > 200:  # safety
            break
    return out


def get_list_fields_by_name(client: ClickUpClient, list_id: str) -> Dict[str, Dict[str, Any]]:
    data = client.get_list_fields(list_id)
    fields = data.get("fields", []) if isinstance(data, dict) else []
    return {f.get("name"): f for f in fields if f.get("name")}


def dropdown_option_id(field: Dict[str, Any], option_name: str) -> Optional[str]:
    type_config = field.get("type_config") or {}
    options = type_config.get("options") or []
    for opt in options:
        if opt.get("name") == option_name:
            return opt.get("id")
    return None


def is_dropdown_field(field: Dict[str, Any]) -> bool:
    type_config = field.get("type_config") or {}
    options = type_config.get("options") or []
    return len(options) > 0


def set_field_value_by_name(
    client: ClickUpClient,
    task_id: str,
    fields_by_name: Dict[str, Dict[str, Any]],
    field_name: str,
    desired_value: Any,
    *,
    strict: bool = False,
) -> None:
    """
    Sets a custom field value by ClickUp field name.
    - Dropdown: maps option label -> option_id
    - Text/Number: sets value directly
    """
    if desired_value is None:
        return
    if isinstance(desired_value, str) and desired_value.strip() == "":
        return

    field = fields_by_name.get(field_name)
    if not field:
        if strict:
            raise RuntimeError(f"Custom field '{field_name}' not found on target List.")
        return

    field_id = field.get("id")
    if not field_id:
        if strict:
            raise RuntimeError(f"Custom field '{field_name}' has no id (unexpected).")
        return

    # Dropdown -> option id
    if is_dropdown_field(field):
        opt_id = dropdown_option_id(field, str(desired_value))
        if not opt_id:
            raise RuntimeError(
                f"Dropdown option '{desired_value}' not found for field '{field_name}'. "
                f"Fix ClickUp dropdown options to match library codes."
            )
        client.set_custom_field_value(task_id, field_id, opt_id)
        return

    # Non-dropdown
    client.set_custom_field_value(task_id, field_id, desired_value)


def extract_task_code_from_task(task: Dict[str, Any], task_code_field_id: str) -> Optional[str]:
    """Reads the Task Code value from the task's custom_fields list."""
    for cf in task.get("custom_fields", []) or []:
        if cf.get("id") == task_code_field_id:
            val = cf.get("value")
            if val is None:
                return None
            return str(val)
    return None


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    s = get_settings()
    lib = load_library(LIB_ROOT)
    profile = load_profile(PROFILE_PATH)

    # 1) Evaluate applicability
    eval_out = evaluate_applicability(lib.applicability_rules, profile)
    matched_rules = eval_out["matched_rules"]
    task_codes = eval_out["final_tasks"]

    # 2) Compile tasks (enrich descriptions)
    compiled = compile_tasks(lib, task_codes, profile, matched_rules)

    # 3) Compute schedule (toggle here)
    DURATION_MODE = "practical"  # or "statutory"
    planned = compute_schedule(
        compiled,
        lib.dependencies,
        profile.plan_start_date,
        duration_mode=DURATION_MODE,
        fallback_to_practical=True,
    )

    # 4) Export local snapshot
    out_dir = ROOT / "outputs" / "project_exports" / profile.project_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for t in compiled:
        p = planned[t.task_code]
        rows.append(
            {
                "task_code": t.task_code,
                "task_name": t.task_name,
                "phase_code": t.phase_code,
                "planned_start": p.planned_start.isoformat(),
                "planned_finish": p.planned_finish.isoformat(),
                "duration_mode": DURATION_MODE,
                "duration_days": p.duration_days,
                "hard_legal_blocker": t.hard_legal_blocker,
                "legal_basis": t.legal_basis,
                "actor_role": t.actor_role,
                "competent_authority": t.competent_authority,
            }
        )

    df = pd.DataFrame(rows).sort_values(["planned_start", "phase_code", "task_code"])
    write_csv(out_dir / "tasks.csv", df)
    write_json(
        out_dir / "tasks.json",
        {
            "project": profile.__dict__,
            "matched_rules": matched_rules,
            "duration_mode": DURATION_MODE,
            "tasks": rows,
        },
    )

    console.print("[bold]Compiled project snapshot[/bold]")
    console.print(f"Project: {profile.project_id} | Tasks: {len(compiled)} | Mode: {DURATION_MODE}")
    console.print(f"Wrote: {out_dir / 'tasks.csv'}")

    # 5) ClickUp upsert
    if not s.clickup_api_token or not s.clickup_target_list_id:
        console.print("[yellow]ClickUp token or CLICKUP_TARGET_LIST_ID missing. Skipping ClickUp write.[/yellow]")
        return

    client = ClickUpClient(base_url=s.clickup_base_url, token=s.clickup_api_token, dry_run=s.dry_run)

    # Load field definitions once
    fields_by_name = get_list_fields_by_name(client, s.clickup_target_list_id)

    # Task Code field is mandatory for idempotent upsert
    if "Task Code" not in fields_by_name:
        console.print("[red]Cannot find 'Task Code' custom field on target list. Create it manually first.[/red]")
        return
    task_code_field_id = fields_by_name["Task Code"]["id"]

    # Fetch existing tasks and build index by Task Code
    existing_tasks = fetch_all_tasks(client, s.clickup_target_list_id, include_closed=True)
    existing_by_task_code: Dict[str, Dict[str, Any]] = {}
    for et in existing_tasks:
        tc_val = extract_task_code_from_task(et, task_code_field_id)
        if tc_val:
            existing_by_task_code[tc_val] = et

    created = 0
    updated = 0
    id_by_task_code: Dict[str, str] = {}

    for t in compiled:
        p = planned[t.task_code]
        name = f"[{t.phase_code}] {t.task_name}"

        payload = {
            "name": name,
            "description": t.description_md,
            "start_date": date_to_ms(p.planned_start),
            "due_date": date_to_ms(p.planned_finish),
        }

        if t.task_code in existing_by_task_code:
            tid = existing_by_task_code[t.task_code]["id"]
            client.put(f"task/{tid}", payload)
            updated += 1
        else:
            res = client.create_task(s.clickup_target_list_id, payload)
            tid = res.get("id") if isinstance(res, dict) else None
            if not tid:
                console.print(f"[red]Failed to create task for {t.task_code}[/red]")
                continue
            created += 1

        id_by_task_code[t.task_code] = tid

        # ✅ Set ALL custom fields (this is what fixes your issue)
        # Task + Phase
        set_field_value_by_name(client, tid, fields_by_name, "Task Code", t.task_code, strict=True)
        set_field_value_by_name(client, tid, fields_by_name, "Phase", t.phase_code)

        # Profile dimensions
        set_field_value_by_name(client, tid, fields_by_name, "Classification", profile.classification)
        set_field_value_by_name(client, tid, fields_by_name, "Environmental Regime", profile.environmental_regime)
        set_field_value_by_name(client, tid, fields_by_name, "Project Type", profile.project_type)
        set_field_value_by_name(client, tid, fields_by_name, "Grid Interaction", profile.grid_interaction)
        set_field_value_by_name(client, tid, fields_by_name, "Capacity Band", profile.capacity_band)
        set_field_value_by_name(client, tid, fields_by_name, "Regulatory Path", profile.regulatory_path)
        set_field_value_by_name(client, tid, fields_by_name, "Location Constraint", profile.location_constraint)

        # Task attributes
        set_field_value_by_name(client, tid, fields_by_name, "Legal Basis", t.legal_basis)
        if t.actor_role:
            set_field_value_by_name(client, tid, fields_by_name, "Actor Role", t.actor_role)
        if t.competent_authority:
            set_field_value_by_name(client, tid, fields_by_name, "Competent Authority", t.competent_authority)

        set_field_value_by_name(
            client,
            tid,
            fields_by_name,
            "Hard Legal Blocker",
            "Yes" if t.hard_legal_blocker else "No",
        )

        if t.statutory_max_days is not None:
            set_field_value_by_name(client, tid, fields_by_name, "Statutory Max Days", float(t.statutory_max_days))
        if t.practical_typical_days is not None:
            set_field_value_by_name(client, tid, fields_by_name, "Practical Typical Days", float(t.practical_typical_days))

    console.print(f"[bold]ClickUp upsert done[/bold] created={created} updated={updated} dry_run={s.dry_run}")

    # 6) Dependencies (best-effort)
    for _, r in lib.dependencies.iterrows():
        pre = str(r["predecessor_task_code"])
        suc = str(r["successor_task_code"])
        if pre in id_by_task_code and suc in id_by_task_code:
            try:
                client.add_dependency(id_by_task_code[suc], id_by_task_code[pre])
            except Exception as e:
                console.print(f"[yellow]Dependency skipped {pre}->{suc}: {e}[/yellow]")

    console.print("[bold]Dependencies applied (best-effort)[/bold]")


if __name__ == "__main__":
    main()
