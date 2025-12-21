from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Tuple

import networkx as nx
import pandas as pd

from regops.workflow.instantiate import CompiledTask


@dataclass
class PlannedTaskDates:
    task_code: str
    planned_start: date
    planned_finish: date
    duration_days: float


def _iso_to_date(s: str) -> date:
    return date.fromisoformat(s)


def compute_schedule(
    compiled_tasks: List[CompiledTask],
    dependencies: pd.DataFrame,
    plan_start_date: str,
    duration_mode: str = "practical",  # "statutory"|"practical"
    fallback_to_practical: bool = True,
) -> Dict[str, PlannedTaskDates]:
    """Compute a simple precedence schedule on a DAG using FS/SS/FF constraints.
    - duration_mode selects which duration to use.
    - if a selected duration is missing and fallback_to_practical is True, use practical typical days.
    """
    start0 = _iso_to_date(plan_start_date)

    task_map = {t.task_code: t for t in compiled_tasks}
    task_codes = list(task_map.keys())

    def get_dur(tc: str) -> float:
        t = task_map[tc]
        if duration_mode == "statutory":
            if t.statutory_max_days is not None:
                return float(t.statutory_max_days)
            if fallback_to_practical and t.practical_typical_days is not None:
                return float(t.practical_typical_days)
            return 0.0
        # practical
        if t.practical_typical_days is not None:
            return float(t.practical_typical_days)
        if t.statutory_max_days is not None:
            return float(t.statutory_max_days)
        return 0.0

    # Build constraint graph for topo ordering (ignoring edge types for acyclicity check)
    g = nx.DiGraph()
    for tc in task_codes:
        g.add_node(tc)

    rels = dependencies[dependencies["predecessor_task_code"].isin(task_codes) & dependencies["successor_task_code"].isin(task_codes)].copy()
    for _, r in rels.iterrows():
        g.add_edge(str(r["predecessor_task_code"]), str(r["successor_task_code"]))

    if not nx.is_directed_acyclic_graph(g):
        raise ValueError("Dependency graph has cycles among selected tasks.")

    order = list(nx.topological_sort(g))

    # Initialize starts
    starts: Dict[str, float] = {tc: 0.0 for tc in order}
    durs: Dict[str, float] = {tc: get_dur(tc) for tc in order}

    # Apply constraints iteratively in topological order (single pass works for DAG with these constraints when preds already settled)
    for tc in order:
        # enforce constraints from predecessors -> tc
        incoming = rels[rels["successor_task_code"] == tc]
        if incoming.empty:
            continue
        best = starts[tc]
        for _, r in incoming.iterrows():
            pre = str(r["predecessor_task_code"])
            dep_type = str(r["dependency_type"])
            lag = r.get("lag_days")
            lag = 0.0 if pd.isna(lag) or lag == "" else float(lag)

            pre_start = starts.get(pre, 0.0)
            pre_finish = pre_start + durs.get(pre, 0.0)

            if dep_type == "FS":
                constraint = pre_finish + lag
            elif dep_type == "SS":
                constraint = pre_start + lag
            elif dep_type == "FF":
                # finish_succ >= finish_pre + lag => start_succ >= finish_pre + lag - dur_succ
                constraint = pre_finish + lag - durs.get(tc, 0.0)
            else:
                constraint = pre_finish + lag

            if constraint > best:
                best = constraint
        starts[tc] = best

    planned: Dict[str, PlannedTaskDates] = {}
    for tc in order:
        s = starts[tc]
        d = durs[tc]
        ps = start0 + timedelta(days=int(round(s)))
        pf = ps + timedelta(days=int(round(d)))
        planned[tc] = PlannedTaskDates(task_code=tc, planned_start=ps, planned_finish=pf, duration_days=d)

    return planned
