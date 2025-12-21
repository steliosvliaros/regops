from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import pandas as pd

from regops.io.load_library import RegOpsLibrary
from regops.workflow.rule_engine import ProjectProfile


@dataclass
class CompiledTask:
    task_code: str
    task_name: str
    phase_code: str
    description_md: str
    hard_legal_blocker: bool
    parallelizable: bool
    default_order: int
    legal_basis: str
    actor_role: str | None
    competent_authority: str | None
    statutory_max_days: float | None
    practical_typical_days: float | None
    practical_p10_days: float | None
    practical_p90_days: float | None
    matched_rule_ids: List[str]


def _aggregate_legal_basis(task_legal_basis: pd.DataFrame, task_code: str) -> str:
    rows = task_legal_basis[task_legal_basis["task_code"] == task_code]
    parts: List[str] = []
    for _, r in rows.iterrows():
        inst = str(r.get("instrument_code", "")).strip()
        art = str(r.get("article_ref", "")).strip()
        if inst == "NO_LEGAL_BASIS":
            parts.append("NO_LEGAL_BASIS")
            continue
        if inst and art:
            parts.append(f"{inst} {art}")
        elif inst:
            parts.append(inst)
    return "; ".join(sorted(set(parts))) if parts else "NO_LEGAL_BASIS"


def _primary_role(task_roles: pd.DataFrame, task_code: str) -> tuple[str | None, str | None]:
    rows = task_roles[task_roles["task_code"] == task_code]
    if rows.empty:
        return None, None
    r0 = rows.iloc[0].to_dict()
    return str(r0.get("actor_role_code") or "") or None, str(r0.get("authority_name") or "") or None


def _pick_statutory_duration(statutory: pd.DataFrame, task_code: str, profile: ProjectProfile, matched_rule_ids: List[str]) -> float | None:
    rows = statutory[statutory["task_code"] == task_code]
    if rows.empty:
        return None
    # Priority: DIM[...] rows that mention classification/environmental_regime matching, then rule_scope matching any matched_rule_ids, else first numeric
    def score(scope: str) -> int:
        s = scope or ""
        sc = 0
        if "classification=" in s:
            if f"classification={profile.classification}" in s or "classification=ANY" in s:
                sc += 3
        if "environmental_regime=" in s:
            if f"environmental_regime={profile.environmental_regime}" in s or "environmental_regime=ANY" in s:
                sc += 2
        if s in matched_rule_ids:
            sc += 2
        return sc

    rows = rows.copy()
    rows["__score"] = rows["rule_scope"].astype(str).apply(score)
    rows = rows.sort_values(["__score"], ascending=False)

    for _, r in rows.iterrows():
        val = r.get("max_days")
        try:
            if pd.isna(val) or val == "":
                continue
            return float(val)
        except Exception:
            continue
    return None


def _pick_practical_duration(practical: pd.DataFrame, task_code: str, profile: ProjectProfile, matched_rule_ids: List[str]) -> tuple[float | None, float | None, float | None]:
    rows = practical[practical["task_code"] == task_code]
    if rows.empty:
        return None, None, None

    def score(scope: str) -> int:
        s = scope or ""
        sc = 0
        if "classification=" in s:
            if f"classification={profile.classification}" in s or "classification=ANY" in s:
                sc += 3
        if "environmental_regime=" in s:
            if f"environmental_regime={profile.environmental_regime}" in s or "environmental_regime=ANY" in s:
                sc += 2
        if s in matched_rule_ids:
            sc += 2
        return sc

    rows = rows.copy()
    rows["__score"] = rows["rule_scope"].astype(str).apply(score)
    rows = rows.sort_values(["__score"], ascending=False)
    r0 = rows.iloc[0]
    def _f(x):
        try:
            if pd.isna(x) or x == "":
                return None
            return float(x)
        except Exception:
            return None
    return _f(r0.get("typical_days")), _f(r0.get("p10_days")), _f(r0.get("p90_days"))


def compile_tasks(lib: RegOpsLibrary, task_codes: List[str], profile: ProjectProfile, matched_rule_ids: List[str]) -> List[CompiledTask]:
    tasks = lib.tasks[lib.tasks["task_code"].isin(task_codes)].copy()
    tasks = tasks.sort_values(["default_order", "task_code"])

    compiled: List[CompiledTask] = []
    for _, t in tasks.iterrows():
        task_code = str(t["task_code"])
        legal_basis = _aggregate_legal_basis(lib.task_legal_basis, task_code)
        actor_role, authority = _primary_role(lib.task_roles, task_code)
        stat = _pick_statutory_duration(lib.statutory_durations, task_code, profile, matched_rule_ids)
        prac_typ, prac_p10, prac_p90 = _pick_practical_duration(lib.practical_durations, task_code, profile, matched_rule_ids)

        md = str(t.get("task_description_md") or "")
        # enrich description with traceability block
        md += "\n\n---\n"
        md += f"**RegOps Traceability**\n\n"
        md += f"- **Task Code:** `{task_code}`\n"
        md += f"- **Profile:** `{profile.project_id}` ({profile.project_type}, {profile.classification}, {profile.environmental_regime})\n"
        md += f"- **Legal Basis:** {legal_basis}\n"
        if stat is not None:
            md += f"- **Statutory Max Days (planned):** {stat}\n"
        if prac_typ is not None:
            md += f"- **Practical Typical Days (overlay):** {prac_typ} (P10={prac_p10}, P90={prac_p90})\n"
        if actor_role:
            md += f"- **Actor Role:** {actor_role}\n"
        if authority:
            md += f"- **Competent Authority:** {authority}\n"
        md += f"- **Matched Rule IDs:** {', '.join(matched_rule_ids)}\n"

        compiled.append(CompiledTask(
            task_code=task_code,
            task_name=str(t.get("task_name")),
            phase_code=str(t.get("phase_code")),
            description_md=md,
            hard_legal_blocker=str(t.get("hard_legal_blocker")).strip().lower() == "yes",
            parallelizable=str(t.get("parallelizable")).strip().lower() == "yes",
            default_order=int(t.get("default_order")),
            legal_basis=legal_basis,
            actor_role=actor_role,
            competent_authority=authority,
            statutory_max_days=stat,
            practical_typical_days=prac_typ,
            practical_p10_days=prac_p10,
            practical_p90_days=prac_p90,
            matched_rule_ids=matched_rule_ids,
        ))
    return compiled
