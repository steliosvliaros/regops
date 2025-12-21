# regops — ClickUp-first Regulatory Operating System (NO DB)

This repository implements **Option C baseline**: a **versioned RegOps Library** (YAML/CSV) + **Python/Jupyter notebooks** that:
- validates the library,
- generates a ClickUp provisioning plan (and best-effort applies it where API allows),
- instantiates a project plan (tasks + dependencies + schedule) into a target ClickUp List,
- syncs ClickUp statuses back and generates reports.

> **Truth model**
> - **Library is authoritative** for definitions, applicability rules, mappings, and overlays.
> - **ClickUp is authoritative** for execution status and actual dates.
> - No database is used.

## Quickstart

### 1) Create a virtualenv (Python 3.11+)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure environment
Copy `.env.example` to `.env` and fill values.
```bash
cp .env.example .env
```

### 3) Run notebooks in order
These are plain Python scripts for reproducibility.

```bash
python notebooks/00_setup_and_smoke_test.py
python notebooks/01_validate_library.py
python notebooks/02_generate_clickup_provision_plan.py
python notebooks/03_apply_clickup_provisioning_optional.py
python notebooks/04_instantiate_project_to_clickup.py
python notebooks/05_sync_status_back_and_reports.py
```

## Notes on ClickUp API constraints
- Updating custom field values must use the **Set Custom Field Value** endpoint, not Update Task. (ClickUp docs)  
- Creating/setting custom statuses is not consistently supported via API; therefore provisioning outputs step-by-step manual instructions and keeps `provision_plan.json` as authoritative.  

## Library layout
See `regops_library/` for:
- `vocab/` controlled vocabularies,
- `workflow/` tasks/dependencies/rules/mappings,
- `rules/` statutory rule attachments,
- `overlay/` practical durations + risks,
- `clickup/` ClickUp mapping definitions,
- `projects/` sample project profiles.

## Outputs
All generated artifacts go to `outputs/`:
- `outputs/audit_snapshots/` validation reports
- `outputs/provision_plans/` provisioning plans and checklists
- `outputs/project_exports/<project_id>/` compiled snapshots
- `outputs/reports/` dashboards, critical path, risk datasets
