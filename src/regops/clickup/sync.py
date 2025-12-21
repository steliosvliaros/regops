from __future__ import annotations

from typing import Any, Dict, List
import pandas as pd

from regops.clickup.client import ClickUpClient


def fetch_all_tasks(client: ClickUpClient, list_id: str, include_closed: bool = True) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    page = 0
    while True:
        data = client.get_tasks(list_id, include_closed=include_closed, page=page)
        batch = data.get("tasks", []) if isinstance(data, dict) else []
        tasks.extend(batch)
        # ClickUp returns last_page? not consistent; stop if empty or less than page size
        if not batch:
            break
        page += 1
        if page > 200:
            break
    return tasks


def tasks_to_status_df(tasks: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for t in tasks:
        rows.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "status": (t.get("status") or {}).get("status"),
            "date_created": t.get("date_created"),
            "date_updated": t.get("date_updated"),
            "due_date": t.get("due_date"),
            "start_date": t.get("start_date"),
            "url": t.get("url"),
        })
    return pd.DataFrame(rows)
