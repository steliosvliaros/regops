from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import pandas as pd
from rich.console import Console

from regops.settings import get_settings
from regops.io.load_library import load_library
from regops.clickup.client import ClickUpClient
from regops.clickup.sync import fetch_all_tasks, tasks_to_status_df
from regops.workflow.critical_path import critical_path
from regops.reports.exports import write_csv, write_json


console = Console()
ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = ROOT / "regops_library"
OUT_DIR = ROOT / "outputs" / "reports"


def main() -> None:
    s = get_settings()
    lib = load_library(LIB_ROOT)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not s.clickup_api_token or not s.clickup_target_list_id:
        console.print("[yellow]ClickUp token or CLICKUP_TARGET_LIST_ID missing. Generating offline reports only.[/yellow]")
        return

    client = ClickUpClient(base_url=s.clickup_base_url, token=s.clickup_api_token, dry_run=False)  # sync is read-only
    tasks = fetch_all_tasks(client, s.clickup_target_list_id, include_closed=True)
    df_status = tasks_to_status_df(tasks)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    write_csv(OUT_DIR / f"{ts}_status_dashboard.csv", df_status)

    # Critical path (using overlay practical typical durations as defaults)
    # Build durations by task name match not reliable; use Task Code custom field if available
    # Best-effort: map by task title prefix or parse description block.
    durations = {}
    for _, r in lib.practical_durations.iterrows():
        durations[str(r["task_code"])] = float(r["typical_days"])

    task_codes = lib.tasks["task_code"].tolist()
    cp = critical_path(task_codes, lib.dependencies, durations)

    cp_df = pd.DataFrame({"critical_path_order": list(range(1, len(cp.critical_path) + 1)), "task_code": cp.critical_path})
    write_csv(OUT_DIR / f"{ts}_critical_path.csv", cp_df)

    # Bottlenecks: highest variance and highest risk
    # Variance proxy: p90 - typical
    pdur = lib.practical_durations.copy()
    if not pdur.empty:
        pdur["variance"] = pdur["p90_days"] - pdur["typical_days"]
        bottlenecks_var = pdur.sort_values("variance", ascending=False).head(20)
        write_csv(OUT_DIR / f"{ts}_bottlenecks_variance_top20.csv", bottlenecks_var)

    risks = lib.risks.copy()
    if not risks.empty:
        # risk heatmap dataset
        heat = risks[["risk_id", "task_code", "probability_1_5", "impact_1_5", "risk_level"]].copy()
        write_csv(OUT_DIR / f"{ts}_risk_heatmap.csv", heat)
        # top risks by P*I
        risks["score"] = risks["probability_1_5"] * risks["impact_1_5"]
        top = risks.sort_values("score", ascending=False).head(20)
        write_csv(OUT_DIR / f"{ts}_top_risks_top20.csv", top)

    write_json(OUT_DIR / f"{ts}_report_summary.json", {
        "task_count_clickup": len(tasks),
        "critical_path_total_duration_days": cp.total_duration,
        "critical_path": cp.critical_path,
    })

    console.print("[bold]Sync & reports complete[/bold]")
    console.print(f"Wrote dashboards to: {OUT_DIR}")

if __name__ == "__main__":
    main()
