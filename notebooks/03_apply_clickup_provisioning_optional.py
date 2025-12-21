from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from rich.console import Console

from regops.settings import get_settings
from regops.clickup.client import ClickUpClient
from regops.clickup.provisioning import best_effort_provision


console = Console()
ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "outputs" / "provision_plans" / "clickup_provision_plan.json"
OUT_DIR = ROOT / "outputs" / "provision_plans"


def main() -> None:
    s = get_settings()
    if not PLAN_PATH.exists():
        raise SystemExit("Provision plan not found. Run 02_generate_clickup_provision_plan.py first.")

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    if not s.clickup_api_token:
        console.print("[yellow]CLICKUP_API_TOKEN not set; writing manual checklist only.[/yellow]")
        out = {"manual_steps": plan.get("manual_steps", []), "missing_custom_fields": plan.get("custom_fields", [])}
    else:
        client = ClickUpClient(base_url=s.clickup_base_url, token=s.clickup_api_token, dry_run=s.dry_run)
        out = best_effort_provision(client, plan, s.clickup_space_id, s.clickup_folder_id, s.clickup_target_list_id)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{ts}_provisioning_check.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print("[bold]Provisioning (best-effort)[/bold]")
    console.print(f"Wrote: {out_path}")
    if out.get("missing_custom_fields"):
        console.print(f"[yellow]Missing custom fields on target list (by name): {len(out['missing_custom_fields'])}[/yellow]")
        for cf in out["missing_custom_fields"][:10]:
            console.print(f" - {cf.get('name')} ({cf.get('type')})")


if __name__ == "__main__":
    main()
