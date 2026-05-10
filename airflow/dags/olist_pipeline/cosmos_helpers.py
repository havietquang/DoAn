from __future__ import annotations

from cosmos import DbtTaskGroup, ExecutionConfig, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import ExecutionMode, TestBehavior

from .constants import DBT_PROFILES_PATH, DBT_PROJECT_DIR


def get_project_config() -> ProjectConfig:
    return ProjectConfig(
        dbt_project_path=DBT_PROJECT_DIR,
    )


def get_profile_config() -> ProfileConfig:
    return ProfileConfig(
        profile_name="olist_profile",
        target_name="dev",
        profiles_yml_filepath=DBT_PROFILES_PATH,
    )


def get_execution_config() -> ExecutionConfig:
    return ExecutionConfig(
        execution_mode=ExecutionMode.LOCAL,
    )


def build_dbt_task_group(group_id: str, select: list[str]) -> DbtTaskGroup:
    return DbtTaskGroup(
        group_id=group_id,
        project_config=get_project_config(),
        profile_config=get_profile_config(),
        execution_config=get_execution_config(),
        render_config=RenderConfig(
            select=select,
            test_behavior=TestBehavior.AFTER_EACH,
        ),
        operator_args={
            "install_deps": True,
        },
    )
