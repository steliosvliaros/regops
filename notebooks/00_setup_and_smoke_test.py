from __future__ import annotations

from pathlib import Path
from rich.console import Console

from regops.settings import get_settings
from regops.io.load_library import load_library
from regops.clickup.client import ClickUpClient


console = Console()

ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = ROOT / "regops_library"

def main() -> None:
    s = get_settings()
    print(s)
    console.print("[bold]RegOps Smoke Test[/bold]")
    console.print(f"Dry run: {s.dry_run}")

    lib = load_library(LIB_ROOT)
    console.print(f"Loaded tasks: {len(lib.tasks)} | deps: {len(lib.dependencies)} | rules: {len(lib.applicability_rules)}")

    if s.clickup_api_token and s.clickup_base_url and (s.clickup_space_id or s.clickup_target_list_id):
        client = ClickUpClient(base_url=s.clickup_base_url, token=s.clickup_api_token, dry_run=s.dry_run)
        if s.clickup_space_id:
            folders = client.get_folders(s.clickup_space_id)
            console.print(f"ClickUp access OK: folders fetched: {len(folders.get('folders', []))}")
        if s.clickup_target_list_id:
            fields = client.get_list_fields(s.clickup_target_list_id)
            console.print(f"Target list fields fetched: {len(fields.get('fields', []))}")
    else:
        console.print("[yellow]ClickUp env not set (token/base_url/space_id or target_list_id). Skipping API check.[/yellow]")

if __name__ == "__main__":
    main()
