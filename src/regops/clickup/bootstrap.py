from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import json
import time


def _norm(s: str) -> str:
    return (s or "").strip().casefold()


@dataclass
class ResolvedClickUpIds:
    team_id: str
    space_id: str
    folder_id: str
    list_id: str
    workspace_name: str
    space_name: str
    folder_name: str
    list_name: str
    template_id: Optional[str] = None


def _pick_team_id(client, team_id: Optional[str], workspace_name: Optional[str]) -> tuple[str, str]:
    if team_id:
        teams = client.get_teams().get("teams", [])
        for t in teams:
            if str(t.get("id")) == str(team_id):
                return str(team_id), str(t.get("name") or "")
        return str(team_id), (workspace_name or "")

    teams = client.get_teams().get("teams", [])
    if not teams:
        raise RuntimeError("No ClickUp workspaces returned by GET /team. Check API token permissions.")

    if workspace_name:
        for t in teams:
            if _norm(t.get("name", "")) == _norm(workspace_name):
                return str(t["id"]), str(t.get("name") or workspace_name)
        names = [t.get("name") for t in teams]
        raise RuntimeError(f"Workspace '{workspace_name}' not found. Available: {names}")

    if len(teams) == 1:
        return str(teams[0]["id"]), str(teams[0].get("name") or "")

    names = [t.get("name") for t in teams]
    raise RuntimeError(f"Multiple workspaces available. Set CLICKUP_WORKSPACE_NAME. Available: {names}")


def ensure_space(client, team_id: str, space_name: str) -> str:
    spaces = client.get_spaces(team_id, archived=False).get("spaces", [])
    for s in spaces:
        if _norm(s.get("name", "")) == _norm(space_name):
            return str(s["id"])
    created = client.create_space(team_id, space_name)
    return str(created["id"])


def ensure_folder(client, space_id: str, folder_name: str) -> str:
    folders = client.get_folders(space_id, archived=False).get("folders", [])
    for f in folders:
        if _norm(f.get("name", "")) == _norm(folder_name):
            return str(f["id"])
    created = client.create_folder(space_id, folder_name)
    return str(created["id"])


def ensure_list(client, folder_id: str, list_name: str, template_id: Optional[str]) -> str:
    lists = client.get_lists(folder_id, archived=False).get("lists", [])
    for l in lists:
        if _norm(l.get("name", "")) == _norm(list_name):
            return str(l["id"])

    if template_id:
        res = client.create_list_from_template(folder_id, template_id, list_name, return_immediately=True)

        list_id = None
        if isinstance(res, dict):
            if "list" in res and isinstance(res["list"], dict) and res["list"].get("id"):
                list_id = res["list"]["id"]
            elif res.get("id"):
                list_id = res["id"]

        if not list_id:
            raise RuntimeError(f"Create list from template returned unexpected response: {res}")

        # Template creation may be async; wait for list to become accessible
        for _ in range(20):
            try:
                client.get_list(str(list_id))
                return str(list_id)
            except Exception:
                time.sleep(1.5)

        return str(list_id)

    created = client.create_list(folder_id, list_name)
    return str(created["id"])


def ensure_clickup_hierarchy(
    client,
    *,
    team_id: Optional[str],
    workspace_name: Optional[str],
    space_name: str,
    folder_name: str,
    list_name: str,
    template_id: Optional[str],
) -> ResolvedClickUpIds:
    if not space_name or not folder_name or not list_name:
        raise RuntimeError("space_name, folder_name, list_name are required for name-first provisioning.")

    resolved_team_id, resolved_workspace_name = _pick_team_id(client, team_id, workspace_name)
    space_id = ensure_space(client, resolved_team_id, space_name)
    folder_id = ensure_folder(client, space_id, folder_name)
    list_id = ensure_list(client, folder_id, list_name, template_id)

    return ResolvedClickUpIds(
        team_id=resolved_team_id,
        space_id=space_id,
        folder_id=folder_id,
        list_id=list_id,
        workspace_name=resolved_workspace_name,
        space_name=space_name,
        folder_name=folder_name,
        list_name=list_name,
        template_id=template_id,
    )


def write_resolved_ids(path: Path, resolved: ResolvedClickUpIds) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(resolved), indent=2, ensure_ascii=False), encoding="utf-8")
