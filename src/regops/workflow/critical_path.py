from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import networkx as nx
import pandas as pd


@dataclass
class CriticalPathResult:
    critical_path: List[str]
    total_duration: float
    longest_path_len_by_task: Dict[str, float]


def critical_path(task_codes: List[str], dependencies: pd.DataFrame, durations: Dict[str, float]) -> CriticalPathResult:
    g = nx.DiGraph()
    for tc in task_codes:
        g.add_node(tc)

    rels = dependencies[dependencies["predecessor_task_code"].isin(task_codes) & dependencies["successor_task_code"].isin(task_codes)]
    for _, r in rels.iterrows():
        pre = str(r["predecessor_task_code"])
        suc = str(r["successor_task_code"])
        g.add_edge(pre, suc)

    if not nx.is_directed_acyclic_graph(g):
        raise ValueError("Graph has cycles; critical path undefined.")

    topo = list(nx.topological_sort(g))
    dist: Dict[str, float] = {tc: durations.get(tc, 0.0) for tc in topo}
    pred: Dict[str, str | None] = {tc: None for tc in topo}

    for tc in topo:
        for suc in g.successors(tc):
            cand = dist[tc] + durations.get(suc, 0.0)
            if cand > dist.get(suc, 0.0):
                dist[suc] = cand
                pred[suc] = tc

    end = max(topo, key=lambda x: dist.get(x, 0.0))
    total = dist.get(end, 0.0)

    # reconstruct
    path: List[str] = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = pred.get(cur)
    path.reverse()

    return CriticalPathResult(critical_path=path, total_duration=total, longest_path_len_by_task=dist)
