from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from rich.console import Console

from regops.clickup.field_mapping import load_clickup_field_map
from regops.clickup.provision_plan import generate_provision_plan


console = Console()
ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "regops_library" / "clickup" / "clickup_field_map.yaml"
OUT_PATH = ROOT / "outputs" / "provision_plans" / "clickup_provision_plan.json"


def main() -> None:
    field_map = load_clickup_field_map(MAP_PATH)
    plan = generate_provision_plan(field_map)

    OUT_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print("[bold]Provision plan generated[/bold]")
    console.print(f"Wrote: {OUT_PATH}")


if __name__ == "__main__":
    main()
