from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Set, Tuple

import pandas as pd

from regops.io.load_library import RegOpsLibrary


@dataclass
class ValidationIssue:
    severity: str  # ERROR/WARN
    code: str
    message: str


def _codes(vocab: Dict[str, Dict[str, Any]], vocab_name: str) -> Set[str]:
    return set(vocab.get(vocab_name, {}).keys())


def validate_unique_task_codes(lib: RegOpsLibrary) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    dupes = lib.tasks["task_code"][lib.tasks["task_code"].duplicated()].tolist()
    if dupes:
        issues.append(ValidationIssue("ERROR", "TASK_DUPLICATE", f"Duplicate task_code(s): {dupes}"))
    return issues


def validate_dependency_references(lib: RegOpsLibrary) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    task_set = set(lib.tasks["task_code"].tolist())
    for _, row in lib.dependencies.iterrows():
        pre = row["predecessor_task_code"]
        suc = row["successor_task_code"]
        if pre not in task_set:
            issues.append(ValidationIssue("ERROR", "DEP_MISSING_TASK", f"Dependency predecessor missing task_code={pre}"))
        if suc not in task_set:
            issues.append(ValidationIssue("ERROR", "DEP_MISSING_TASK", f"Dependency successor missing task_code={suc}"))
        if row["dependency_type"] not in {"FS", "SS", "FF"}:
            issues.append(ValidationIssue("ERROR", "DEP_BAD_TYPE", f"Bad dependency_type for {pre}->{suc}: {row['dependency_type']}"))
    return issues


def validate_vocab_usage_in_rules(lib: RegOpsLibrary) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    # applicability_rules.yaml must only use vocab codes or ANY
    valid = {
        "classification": _codes(lib.vocab, "project_classification"),
        "project_type": _codes(lib.vocab, "project_type"),
        "grid_interaction": _codes(lib.vocab, "grid_interaction"),
        "capacity_band": _codes(lib.vocab, "capacity_band"),
        "regulatory_path": _codes(lib.vocab, "regulatory_path"),
        "location_constraint": _codes(lib.vocab, "location_constraint"),
        "environmental_regime": _codes(lib.vocab, "environmental_regime"),
    }
    for rule in lib.applicability_rules:
        rid = rule.get("rule_id", "?")
        match = rule.get("match", {})
        for dim, allowed in valid.items():
            vals = match.get(dim, ["ANY"])
            for v in vals:
                if v == "ANY":
                    continue
                if v not in allowed:
                    issues.append(ValidationIssue("ERROR", "RULE_BAD_VOCAB",
                        f"Rule {rid}: value '{v}' not in vocab for '{dim}'"))
    return issues


def validate_tasks_have_legal_basis_or_marker(lib: RegOpsLibrary) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    task_set = set(lib.tasks["task_code"].tolist())
    basis = lib.task_legal_basis
    # Explicit marker accepted: instrument_code == 'NO_LEGAL_BASIS'
    for tc in task_set:
        rows = basis[basis["task_code"] == tc]
        if rows.empty:
            issues.append(ValidationIssue("ERROR", "NO_LEGAL_BASIS_POINTER",
                f"Task {tc} has no legal basis pointer and no NO_LEGAL_BASIS marker."))
        else:
            # if present but all empty strings?
            ok = False
            for _, r in rows.iterrows():
                inst = str(r.get("instrument_code", "")).strip()
                if inst:
                    ok = True
                    break
            if not ok:
                issues.append(ValidationIssue("ERROR", "EMPTY_LEGAL_BASIS_POINTER",
                    f"Task {tc} has legal basis row(s) but no instrument_code populated."))
    # Also ensure pointers reference known instruments OR NO_LEGAL_BASIS
    known_insts = set()
    # instrument register is optional in this minimal repo; accept anything starting with GR_ or EU_ or NO_LEGAL_BASIS
    for _, r in basis.iterrows():
        inst = str(r.get("instrument_code", "")).strip()
        if inst == "NO_LEGAL_BASIS":
            continue
        if not inst:
            issues.append(ValidationIssue("ERROR", "LEGAL_BASIS_MISSING_INST", f"Missing instrument_code in task_legal_basis row for task={r.get('task_code')}"))
    return issues


def validate_hard_blockers_have_classification_aware_rules_or_explicit_none(lib: RegOpsLibrary) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    hard = lib.tasks[lib.tasks["hard_legal_blocker"].str.lower() == "yes"]["task_code"].tolist()
    sd = lib.statutory_durations.copy()
    if sd.empty:
        issues.append(ValidationIssue("ERROR", "NO_STATUTORY_DURATIONS", "rules/statutory_durations.csv missing or empty."))
        return issues

    for tc in hard:
        rows = sd[sd["task_code"] == tc]
        if rows.empty:
            issues.append(ValidationIssue("ERROR", "HARD_BLOCKER_NO_RULE", f"Hard blocker task {tc} has no statutory_durations row (explicit none required)."))
            continue
        # classification-aware means rule_scope contains 'classification=' or uses a known rule_id that implies classification branching.
        found = False
        for _, r in rows.iterrows():
            scope = str(r.get("rule_scope", "")).strip()
            notes = str(r.get("notes", "")).strip().lower()
            if "classification=" in scope:
                found = True
                break
            if "no statutory deadline" in notes:
                found = True
                break
        if not found:
            issues.append(ValidationIssue("WARN", "HARD_BLOCKER_RULE_NOT_CLASS_AWARE",
                f"Hard blocker {tc} has statutory rows but none appear classification-aware; consider adding DIM[classification=...] or explicit 'No statutory deadline' note."))
    return issues


def run_all_validations(lib: RegOpsLibrary) -> Dict[str, Any]:
    issues: List[ValidationIssue] = []
    issues += validate_unique_task_codes(lib)
    issues += validate_dependency_references(lib)
    issues += validate_vocab_usage_in_rules(lib)
    issues += validate_tasks_have_legal_basis_or_marker(lib)
    issues += validate_hard_blockers_have_classification_aware_rules_or_explicit_none(lib)

    summary = {
        "errors": sum(1 for i in issues if i.severity == "ERROR"),
        "warnings": sum(1 for i in issues if i.severity == "WARN"),
    }
    return {
        "summary": summary,
        "issues": [i.__dict__ for i in issues],
    }
