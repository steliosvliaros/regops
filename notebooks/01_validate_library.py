from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from rich.console import Console

from regops.io.load_library import load_library
from regops.validation.validators import run_all_validations


console = Console()
ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = ROOT / "regops_library"
OUT_DIR = ROOT / "outputs" / "audit_snapshots"


def main() -> None:
    lib = load_library(LIB_ROOT)
    report = run_all_validations(lib)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{ts}_validation_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print("[bold]Library Validation[/bold]")
    console.print(f"Errors: {report['summary']['errors']} | Warnings: {report['summary']['warnings']}")
    console.print(f"Wrote: {out_path}")

    if report["summary"]["errors"] > 0:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
