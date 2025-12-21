from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class ClickUpClient:
    base_url: str
    token: str
    dry_run: bool = True

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        if self.dry_run and method.upper() in {"POST", "PUT", "DELETE"}:
            return {"dry_run": True, "method": method, "url": url, "params": params, "json": json_body}

        for attempt in range(5):
            resp = requests.request(method=method, url=url, headers=self._headers(), params=params, json=json_body, timeout=60)
            if resp.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"ClickUp API error {resp.status_code}: {resp.text}")
            return resp.json() if resp.text else {}
        raise RuntimeError("ClickUp API rate-limited too many times (429).")

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.request("GET", path, params=params)

    def post(self, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", path, json_body=json_body)

    def put(self, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("PUT", path, json_body=json_body)

    # --- convenience methods ---
    def get_folders(self, space_id: str) -> Dict[str, Any]:
        return self.get(f"space/{space_id}/folder")

    def get_folder_lists(self, folder_id: str) -> Dict[str, Any]:
        return self.get(f"folder/{folder_id}/list")

    def get_list_fields(self, list_id: str) -> Dict[str, Any]:
        return self.get(f"list/{list_id}/field")

    def create_task(self, list_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post(f"list/{list_id}/task", payload)

    def get_tasks(self, list_id: str, include_closed: bool = True, page: int = 0) -> Dict[str, Any]:
        return self.get(f"list/{list_id}/task", params={"include_closed": str(include_closed).lower(), "page": page})

    def set_custom_field_value(self, task_id: str, field_id: str, value: Any) -> Dict[str, Any]:
        # docs: POST /task/{task_id}/field/{field_id}
        return self.post(f"task/{task_id}/field/{field_id}", {"value": value})

    def add_dependency(self, task_id: str, depends_on: str) -> Dict[str, Any]:
        # docs: POST /task/{task_id}/dependency {depends_on: <id>}
        return self.post(f"task/{task_id}/dependency", {"depends_on": depends_on})
