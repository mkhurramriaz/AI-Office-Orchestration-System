import uuid
from typing import Sequence
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.project import Project
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)

    async def create_project(self, project_in: ProjectCreate, current_user: User) -> Project:
        """Create a new project. Allowed for MANAGER and ADMIN."""
        if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Managers and Administrators can create projects.",
            )

        project = Project(
            project_name=project_in.project_name,
            description=project_in.description,
            original_brief=project_in.original_brief,
            start_date=project_in.start_date,
            deadline=project_in.deadline,
            created_by=current_user.id,
        )
        return await self.project_repo.create(project)

    async def get_project(self, project_id: uuid.UUID, current_user: User) -> Project:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        # Access check: ADMIN can access any project
        if current_user.role == UserRole.ADMIN:
            return project
        # MANAGER can access their own projects
        if current_user.role == UserRole.MANAGER and project.created_by == current_user.id:
            return project
        # EMPLOYEE can access projects they are assigned to
        if current_user.role == UserRole.EMPLOYEE:
            emp_projects = await self.project_repo.get_employee_projects(current_user.id)
            if any(p.id == project.id for p in emp_projects):
                return project

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this project.",
        )

    async def list_projects(
        self,
        current_user: User,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Project], int]:
        if current_user.role == UserRole.ADMIN:
            projects = await self.project_repo.get_recent(skip=skip, limit=limit)
            total = await self.project_repo.count()
            return projects, total
        elif current_user.role == UserRole.MANAGER:
            projects = await self.project_repo.get_by_manager(current_user.id, skip=skip, limit=limit)
            total = await self.project_repo.count(created_by=current_user.id)
            return projects, total
        else:
            projects = await self.project_repo.get_employee_projects(current_user.id, skip=skip, limit=limit)
            return projects, len(projects)

    async def update_project(self, project_id: uuid.UUID, project_in: ProjectUpdate, current_user: User) -> Project:
        project = await self.get_project(project_id, current_user)
        if current_user.role != UserRole.ADMIN and project.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project creator or an Administrator can modify this project.",
            )

        update_data = project_in.model_dump(exclude_unset=True)
        return await self.project_repo.update(project, **update_data)

    async def delete_project(self, project_id: uuid.UUID, current_user: User) -> None:
        project = await self.get_project(project_id, current_user)
        if current_user.role != UserRole.ADMIN and project.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project creator or an Administrator can delete this project.",
            )
        await self.project_repo.delete(project)
