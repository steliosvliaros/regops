from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ClickUp
    clickup_api_token: str = Field(default="", alias="CLICKUP_API_TOKEN")
    clickup_base_url: str = Field(default="https://api.clickup.com/api/v2", alias="CLICKUP_BASE_URL")
    clickup_team_id: str = Field(default="", alias="CLICKUP_TEAM_ID")
    clickup_space_id: str = Field(default="", alias="CLICKUP_SPACE_ID")
    clickup_folder_id: str = Field(default="", alias="CLICKUP_FOLDER_ID")
    clickup_template_list_id: str = Field(default="", alias="CLICKUP_TEMPLATE_LIST_ID")
    clickup_target_list_id: str = Field(default="", alias="CLICKUP_TARGET_LIST_ID")

    # behavior
    dry_run: bool = Field(default=True, alias="REGOPS_DRY_RUN")
    log_level: str = Field(default="INFO", alias="REGOPS_LOG_LEVEL")


def get_settings() -> Settings:
    return Settings()
