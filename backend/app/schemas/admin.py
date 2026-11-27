from pydantic import BaseModel


class AdminOverviewResponse(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    users_by_account_role: dict[str, int]
    employees_by_department: dict[str, int]
    employees_by_professional_role: dict[str, int]
    total_projects: int
    projects_by_status: dict[str, int]
    total_tasks: int
    tasks_by_status: dict[str, int]
