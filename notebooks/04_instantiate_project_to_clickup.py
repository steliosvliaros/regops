from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

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
PROFILE_PATH = LIB_ROOT / "projects" / "project_profile_example.yaml"


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


def resolve_field_id_by_name(client: ClickUpClient, list_id: str, field_name: str) -> str | None:
    data = client.get_list_fields(list_id)
    for f in data.get("fields", []):
        if f.get("name") == field_name:
            return f.get("id")
    return None


def main() -> None:
    s = get_settings()
    lib = load_library(LIB_ROOT)
    profile = load_profile(PROFILE_PATH)

    eval_out = evaluate_applicability(lib.applicability_rules, profile)
    matched = eval_out["matched_rules"]
    task_codes = eval_out["final_tasks"]

    compiled = compile_tasks(lib, task_codes, profile, matched)

    # toggle schedule mode here:
    DURATION_MODE = "practical"  # or "statutory"
    planned = compute_schedule(compiled, lib.dependencies, profile.plan_start_date, duration_mode=DURATION_MODE, fallback_to_practical=True)

    # Export local snapshot
    out_dir = ROOT / "outputs" / "project_exports" / profile.project_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for t in compiled:
        p = planned[t.task_code]
        rows.append({
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
        })
    df = pd.DataFrame(rows).sort_values(["planned_start", "phase_code", "task_code"])
    write_csv(out_dir / "tasks.csv", df)

    # also JSON
    write_json(out_dir / "tasks.json", {
        "project": profile.__dict__,
        "matched_rules": matched,
        "duration_mode": DURATION_MODE,
        "tasks": rows,
    })

    console.print("[bold]Compiled project snapshot[/bold]")
    console.print(f"Project: {profile.project_id} | Tasks: {len(compiled)} | Mode: {DURATION_MODE}")
    console.print(f"Wrote: {out_dir / 'tasks.csv'}")

    # ClickUp upsert
    if not s.clickup_api_token or not s.clickup_target_list_id:
        console.print("[yellow]ClickUp token or CLICKUP_TARGET_LIST_ID missing. Skipping ClickUp write.[/yellow]")
        return

    client = ClickUpClient(base_url=s.clickup_base_url, token=s.clickup_api_token, dry_run=s.dry_run)

    # Resolve custom field IDs by name (Task Code etc.)
    task_code_field_id = resolve_field_id_by_name(client, s.clickup_target_list_id, "Task Code")

    if not task_code_field_id:
        console.print("[red]Cannot find 'Task Code' custom field on target list. Create it manually first.[/red]")
        return

    # Fetch existing tasks to upsert by Task Code (best-effort: name match fallback)
    existing_tasks = client.get_tasks(s.clickup_target_list_id, include_closed=True, page=0).get("tasks", [])
    existing_by_task_code: Dict[str, Dict[str, Any]] = {}

    # Try to read task_code from custom_fields if present
    for et in existing_tasks:
        cfs = et.get("custom_fields", []) or []
        tc_val = None
        for cf in cfs:
            if cf.get("id") == task_code_field_id:
                tc_val = (cf.get("value") or "")
        if tc_val:
            existing_by_task_code[str(tc_val)] = et

    created = 0
    updated = 0
    id_by_task_code: Dict[str, str] = {}

    for t in compiled:
        p = planned[t.task_code]
        name = f"[{t.phase_code}] {t.task_name}"
        payload = {
            "name": name,
            "description": t.description_md,
            # ClickUp uses ms timestamps; keep planned dates in description and optionally set due_date/start_date
            "start_date": int(p.planned_start.strftime("%s")) * 1000,
            "due_date": int(p.planned_finish.strftime("%s")) * 1000,
        }

        # upsert behavior: create new task if not found by Task Code (best-effort)
        if t.task_code in existing_by_task_code:
            # Update task core fields
            tid = existing_by_task_code[t.task_code]["id"]
            client.put(f"task/{tid}", payload)
            updated += 1
            id_by_task_code[t.task_code] = tid
        else:
            res = client.create_task(s.clickup_target_list_id, payload)
            tid = res.get("id") if isinstance(res, dict) else None
            if tid:
                created += 1
                id_by_task_code[t.task_code] = tid
                # set Task Code custom field (must use Set Custom Field Value endpoint)
                client.set_custom_field_value(tid, task_code_field_id, t.task_code)

    console.print(f"[bold]ClickUp upsert done[/bold] created={created} updated={updated} dry_run={s.dry_run}")

    # Dependencies (best-effort; requires task IDs for both ends)
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
