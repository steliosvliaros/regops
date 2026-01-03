from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All configuration comes from environment variables / .env.
    No secrets in code.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ClickUp API
    clickup_api_token: Optional[str] = Field(default=None, alias="CLICKUP_API_TOKEN")
    clickup_base_url: str = Field(default="https://api.clickup.com/api/v2", alias="CLICKUP_BASE_URL")

    # Optional IDs (classic mode)
    clickup_team_id: Optional[str] = Field(default=None, alias="CLICKUP_TEAM_ID")
    clickup_space_id: Optional[str] = Field(default=None, alias="CLICKUP_SPACE_ID")
    clickup_folder_id: Optional[str] = Field(default=None, alias="CLICKUP_FOLDER_ID")
    clickup_target_list_id: Optional[str] = Field(default=None, alias="CLICKUP_TARGET_LIST_ID")
    clickup_template_list_id: Optional[str] = Field(default=None, alias="CLICKUP_TEMPLATE_LIST_ID")

    # Name-first provisioning
    clickup_workspace_name: Optional[str] = Field(default=None, alias="CLICKUP_WORKSPACE_NAME")
    clickup_space_name: Optional[str] = Field(default=None, alias="CLICKUP_SPACE_NAME")
    clickup_folder_name: Optional[str] = Field(default=None, alias="CLICKUP_FOLDER_NAME")
    clickup_project_list_name: Optional[str] = Field(default=None, alias="CLICKUP_PROJECT_LIST_NAME")
    clickup_list_template_id: Optional[str] = Field(default=None, alias="CLICKUP_LIST_TEMPLATE_ID")

    # Runtime
    dry_run: bool = Field(default=True, alias="REGOPS_DRY_RUN")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
