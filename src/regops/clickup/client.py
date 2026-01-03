from __future__ import annotations

import hashlib
import json as jsonlib
from typing import Any, Dict, Optional

import requests
from rich.console import Console

console = Console()


class ClickUpError(RuntimeError):
    pass


class ClickUpClient:
    """
    Minimal ClickUp API v2 client with dry-run support.
    """

    def __init__(self, *, base_url: str, token: str, dry_run: bool = False, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.dry_run = dry_run
        self.timeout = timeout

    # ---------------------------
    # Low-level helpers
    # ---------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        return f"{self.base_url}/{path}"

    def _fake_id(self, seed: str) -> str:
        h = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
        return f"DRY-{h}"

    def request(self, method: str, path: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> Any:
        url = self._url(path)

        is_mutation = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        if self.dry_run and is_mutation:
            console.print(f"[cyan][DRY RUN][/cyan] {method.upper()} {url}")
            if params:
                console.print(f"[cyan]params:[/cyan] {params}")
            if json is not None:
                console.print(f"[cyan]json:[/cyan] {json}")
            # Return shape similar to ClickUp where possible
            if "list_template" in path or path.endswith("/list") or "/task" in path or "/space" in path or "/folder" in path:
                return {"id": self._fake_id(method + url + jsonlib.dumps(json or {}, sort_keys=True))}
            return {"ok": True}

        try:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except Exception as e:
            raise ClickUpError(f"ClickUp request failed: {method} {url} :: {e}") from e

        if resp.status_code >= 400:
            raise ClickUpError(f"ClickUp API error {resp.status_code} for {method} {url}: {resp.text}")

        if not resp.text:
            return {}
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def get(self, path: str, *, params: Optional[dict] = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: dict) -> Any:
        return self.request("POST", path, json=body)

    def put(self, path: str, body: dict) -> Any:
        return self.request("PUT", path, json=body)

    # ---------------------------
    # Core task APIs
    # ---------------------------
    def create_task(self, list_id: str, payload: dict) -> Any:
        # POST /list/{list_id}/task
        return self.post(f"list/{list_id}/task", payload)

    def update_task(self, task_id: str, payload: dict) -> Any:
        # PUT /task/{task_id}
        return self.put(f"task/{task_id}", payload)

    def get_tasks(self, list_id: str, *, include_closed: bool = True, page: int = 0) -> Any:
        # GET /list/{list_id}/task?include_closed=true&page=0
        params = {"include_closed": str(include_closed).lower(), "page": page}
        return self.get(f"list/{list_id}/task", params=params)

    def get_list_fields(self, list_id: str) -> Any:
        # GET /list/{list_id}/field
        return self.get(f"list/{list_id}/field")

    def set_custom_field_value(self, task_id: str, field_id: str, value: Any) -> Any:
        # POST /task/{task_id}/field/{field_id}
        # Body: {"value": ...}
        return self.post(f"task/{task_id}/field/{field_id}", {"value": value})

    def add_dependency(self, task_id: str, depends_on_task_id: str) -> Any:
        # POST /task/{task_id}/dependency
        # Body: {"depends_on": "<task_id>"}
        return self.post(f"task/{task_id}/dependency", {"depends_on": depends_on_task_id})

    # ---------------------------
    # Hierarchy provisioning APIs
    # ---------------------------
    def get_teams(self) -> Any:
        # GET /team
        return self.get("team")

    def get_spaces(self, team_id: str, *, archived: bool = False) -> Any:
        # GET /team/{team_id}/space?archived=false
        return self.get(f"team/{team_id}/space", params={"archived": str(archived).lower()})

    def create_space(self, team_id: str, name: str) -> Any:
        # POST /team/{team_id}/space
        body = {
            "name": name,
            "multiple_assignees": True,
            "features": {
                "due_dates": {
                    "enabled": True,
                    "start_date": True,
                    "remap_due_dates": True,
                    "remap_closed_due_date": True,
                },
                "time_tracking": {"enabled": True},
                "tags": {"enabled": True},
                "time_estimates": {"enabled": True},
                "checklists": {"enabled": True},
                "custom_fields": {"enabled": True},
                "remap_dependencies": {"enabled": True},
                "dependency_warning": {"enabled": True},
                "portfolios": {"enabled": True},
            },
        }
        return self.post(f"team/{team_id}/space", body)

    def get_folders(self, space_id: str, *, archived: bool = False) -> Any:
        # GET /space/{space_id}/folder?archived=false
        return self.get(f"space/{space_id}/folder", params={"archived": str(archived).lower()})

    def create_folder(self, space_id: str, name: str) -> Any:
        # POST /space/{space_id}/folder
        return self.post(f"space/{space_id}/folder", {"name": name})

    def get_lists(self, folder_id: str, *, archived: bool = False) -> Any:
        # GET /folder/{folder_id}/list?archived=false
        return self.get(f"folder/{folder_id}/list", params={"archived": str(archived).lower()})

    def create_list(self, folder_id: str, name: str) -> Any:
        # POST /folder/{folder_id}/list
        return self.post(f"folder/{folder_id}/list", {"name": name})

    def create_list_from_template(self, folder_id: str, template_id: str, name: str, *, return_immediately: bool = True) -> Any:
        # POST /folder/{folder_id}/list_template/{template_id}
        body = {"name": name, "options": {"return_immediately": return_immediately}}
        return self.post(f"folder/{folder_id}/list_template/{template_id}", body)

    def get_list(self, list_id: str) -> Any:
        # GET /list/{list_id}
        return self.get(f"list/{list_id}")
