from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import yaml


@dataclass(frozen=True)
class RegOpsLibrary:
    root: Path
    vocab: Dict[str, Dict[str, Any]]
    tasks: pd.DataFrame
    dependencies: pd.DataFrame
    applicability_rules: List[Dict[str, Any]]
    task_legal_basis: pd.DataFrame
    task_roles: pd.DataFrame
    statutory_durations: pd.DataFrame
    authority_deadlines: pd.DataFrame
    silent_approvals: pd.DataFrame
    public_consultation: pd.DataFrame
    waiting_periods: pd.DataFrame
    appeal_windows: pd.DataFrame
    publication_notification_obligations: pd.DataFrame
    practical_durations: pd.DataFrame
    risks: pd.DataFrame
    mitigation_library: pd.DataFrame


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_vocab(vocab_dir: Path) -> Dict[str, Dict[str, Any]]:
    vocab: Dict[str, Dict[str, Any]] = {}
    for p in sorted(vocab_dir.glob("*.yaml")):
        data = _read_yaml(p)
        items = data.get("items", [])
        vocab[p.stem] = {item["code"]: item for item in items}
    return vocab


def load_library(root: Path) -> RegOpsLibrary:
    root = root.resolve()

    vocab = load_vocab(root / "vocab")

    wf_dir = root / "workflow"
    rules_dir = root / "rules"
    overlay_dir = root / "overlay"

    tasks = _read_csv(wf_dir / "tasks.csv")
    dependencies = _read_csv(wf_dir / "dependencies.csv")
    applicability_rules = _read_yaml(wf_dir / "applicability_rules.yaml")
    task_legal_basis = _read_csv(wf_dir / "task_legal_basis.csv")
    task_roles = _read_csv(wf_dir / "task_roles.csv")

    statutory_durations = _read_csv(rules_dir / "statutory_durations.csv")
    authority_deadlines = _read_csv(rules_dir / "authority_deadlines.csv")
    silent_approvals = _read_csv(rules_dir / "silent_approvals.csv")
    public_consultation = _read_csv(rules_dir / "public_consultation.csv")
    waiting_periods = _read_csv(rules_dir / "waiting_periods.csv")
    appeal_windows = _read_csv(rules_dir / "appeal_windows.csv")
    publication_notification_obligations = _read_csv(rules_dir / "publication_notification_obligations.csv")

    practical_durations = _read_csv(overlay_dir / "practical_durations.csv")
    risks = _read_csv(overlay_dir / "risks.csv")
    mitigation_library = _read_csv(overlay_dir / "mitigation_library.csv")

    return RegOpsLibrary(
        root=root,
        vocab=vocab,
        tasks=tasks,
        dependencies=dependencies,
        applicability_rules=applicability_rules,
        task_legal_basis=task_legal_basis,
        task_roles=task_roles,
        statutory_durations=statutory_durations,
        authority_deadlines=authority_deadlines,
        silent_approvals=silent_approvals,
        public_consultation=public_consultation,
        waiting_periods=waiting_periods,
        appeal_windows=appeal_windows,
        publication_notification_obligations=publication_notification_obligations,
        practical_durations=practical_durations,
        risks=risks,
        mitigation_library=mitigation_library,
    )
