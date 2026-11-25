import uuid
from collections import defaultdict
from typing import Sequence
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import utc_now
from app.models.enums import ActorType, NotificationType, TaskStatus, UserRole
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_history_repository import TaskHistoryRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.task_repo = TaskRepository(session)
        self.project_repo = ProjectRepository(session)
        self.user_repo = UserRepository(session)
        self.history_repo = TaskHistoryRepository(session)
        self.notification_repo = NotificationRepository(session)

    async def _detect_cycle(
        self,
        project_id: uuid.UUID,
        new_edges: list[tuple[uuid.UUID, uuid.UUID]],
    ) -> None:
        """
        Detect circular dependencies in project DAG using DFS 3-color algorithm.
        Edge (A, B) represents 'A depends on B' (B must precede A).
        """
        all_edges = await self.task_repo.get_all_project_dependencies(project_id)
        combined_edges = all_edges + new_edges

        adj: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        all_nodes: set[uuid.UUID] = set()
        for u, v in combined_edges:
            adj[u].append(v)
            all_nodes.add(u)
            all_nodes.add(v)

        # 0 = unvisited, 1 = visiting (in recursion stack), 2 = visited
        visited: dict[uuid.UUID, int] = defaultdict(int)

        def dfs(node: uuid.UUID) -> bool:
            visited[node] = 1
            for neighbor in adj[node]:
                if visited[neighbor] == 1:
                    return True  # Cycle detected
                if visited[neighbor] == 0:
                    if dfs(neighbor):
                        return True
            visited[node] = 2
            return False

        for node in all_nodes:
            if visited[node] == 0:
                if dfs(node):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Circular dependency detected: adding this prerequisite would create a closed dependency loop.",
                    )

    async def create_task(self, task_in: TaskCreate, current_user: User) -> Task:
        """Create a new project task with validation, dependency checking, and audit logging."""
        project = await self.project_repo.get_by_id(task_in.project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        # Permission check: Creator or Admin
        if current_user.role != UserRole.ADMIN and project.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project creator or an Administrator can add tasks.",
            )

        # Check task code uniqueness within project
        existing_code = await self.task_repo.get_by_project_and_code(task_in.project_id, task_in.task_code)
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task code '{task_in.task_code}' already exists in this project.",
            )

        # Validate assignee if provided
        assigned_to_id = None
        assigned_by_id = None
        if task_in.assigned_to:
            assignee = await self.user_repo.get_by_id(task_in.assigned_to)
            if not assignee or not assignee.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user not found or inactive.")
            assigned_to_id = assignee.id
            assigned_by_id = current_user.id

        # Validate prerequisite tasks
        if task_in.depends_on_task_ids:
            for dep_id in task_in.depends_on_task_ids:
                dep_task = await self.task_repo.get_by_id(dep_id)
                if not dep_task:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prerequisite task '{dep_id}' not found.")
                if dep_task.project_id != task_in.project_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Prerequisite task '{dep_task.task_code}' belongs to a different project.",
                    )

        # Instantiate task
        task = Task(
            project_id=task_in.project_id,
            task_code=task_in.task_code,
            title=task_in.title,
            description=task_in.description,
            department=task_in.department,
            required_role=task_in.required_role,
            priority=task_in.priority,
            status=task_in.status,
            assigned_to=assigned_to_id,
            assigned_by=assigned_by_id,
            acceptance_criteria=task_in.acceptance_criteria,
        )
        task = await self.task_repo.create(task)

        # Attach dependencies and verify cycle
        if task_in.depends_on_task_ids:
            new_edges = [(task.id, dep_id) for dep_id in task_in.depends_on_task_ids]
            await self._detect_cycle(task_in.project_id, new_edges)
            for dep_id in task_in.depends_on_task_ids:
                await self.task_repo.add_dependency(task.id, dep_id)

        # Audit history (append-only)
        await self.history_repo.create(
            task_id=task.id,
            actor_id=current_user.id,
            actor_type=ActorType.HUMAN,
            action="CREATED",
            old_status=None,
            new_status=task.status.value,
            description=f"Task {task.task_code} created.",
        )

        # Notification if assigned immediately
        if assigned_to_id and assigned_to_id != current_user.id:
            await self.notification_repo.create_notification(
                recipient_id=assigned_to_id,
                title="New Task Assigned",
                message=f"You have been assigned to task '{task.task_code}: {task.title}' in project '{project.project_name}'.",
                notification_type=NotificationType.TASK_ASSIGNED,
            )

        return (await self.task_repo.get_by_id_with_deps(task.id)) or task

    async def get_task(self, task_id: uuid.UUID, current_user: User) -> Task:
        task = await self.task_repo.get_by_id_with_deps(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

        # Permissions check
        if current_user.role == UserRole.ADMIN:
            return task
        if current_user.role == UserRole.EMPLOYEE:
            if task.assigned_to != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to other employees' tasks.")
            return task

        # MANAGER must own the project
        project = await self.project_repo.get_by_id(task.project_id)
        if not project or project.created_by != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to tasks outside your projects.")

        return task

    async def list_tasks(
        self,
        current_user: User,
        project_id: uuid.UUID | None = None,
        status_filter: TaskStatus | None = None,
        assigned_to: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Task]:
        if current_user.role == UserRole.EMPLOYEE:
            # Employee only sees tasks assigned to themselves
            return await self.task_repo.get_employee_tasks(
                employee_id=current_user.id,
                skip=skip,
                limit=limit,
                status=status_filter,
            )

        if project_id:
            project = await self.project_repo.get_by_id(project_id)
            if not project:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
            if current_user.role == UserRole.MANAGER and project.created_by != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this project's tasks.")

            return await self.task_repo.get_project_tasks(
                project_id=project_id,
                skip=skip,
                limit=limit,
                status=status_filter,
                assigned_to=assigned_to,
            )

        # If no project_id specified and user is Manager
        if current_user.role == UserRole.MANAGER:
            # Fetch tasks across all projects owned by manager
            mgr_projects = await self.project_repo.get_by_manager(current_user.id)
            all_tasks: list[Task] = []
            for p in mgr_projects:
                p_tasks = await self.task_repo.get_project_tasks(p.id, skip=0, limit=limit, status=status_filter)
                all_tasks.extend(p_tasks)
            return all_tasks[skip : skip + limit]

        # Admin: get multi
        filters = {}
        if status_filter:
            filters["status"] = status_filter
        if assigned_to:
            filters["assigned_to"] = assigned_to
        return await self.task_repo.get_multi(skip=skip, limit=limit, **filters)

    async def assign_task(
        self,
        task_id: uuid.UUID,
        employee_id: uuid.UUID,
        current_user: User,
    ) -> Task:
        """Assign task to an employee with department validation, audit recording, and notifications."""
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

        project = await self.project_repo.get_by_id(task.project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        if current_user.role != UserRole.ADMIN and project.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project manager or an Administrator can assign tasks.",
            )

        employee = await self.user_repo.get_by_id(employee_id)
        if not employee or not employee.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found or inactive.")

        old_assignee_id = task.assigned_to
        task.assigned_to = employee.id
        task.assigned_by = current_user.id
        await self.task_repo.session.flush()

        # Audit history in same transaction
        await self.history_repo.create(
            task_id=task.id,
            actor_id=current_user.id,
            actor_type=ActorType.HUMAN,
            action="ASSIGNED",
            old_status=task.status.value,
            new_status=task.status.value,
            description=f"Assigned to {employee.full_name} ({employee.email}).",
        )

        # Notify employee
        if employee.id != current_user.id:
            await self.notification_repo.create_notification(
                recipient_id=employee.id,
                title="Task Assignment",
                message=f"You have been assigned to task '{task.task_code}: {task.title}'.",
                notification_type=NotificationType.TASK_ASSIGNED,
            )

        return (await self.task_repo.get_by_id_with_deps(task.id)) or task

    async def update_task_status(
        self,
        task_id: uuid.UUID,
        new_status: TaskStatus,
        completion_notes: str | None,
        current_user: User,
    ) -> Task:
        """
        Transition task status with dependency completion validation and audit trail.
        A task CANNOT be completed if any prerequisite task is not completed!
        """
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

        project = await self.project_repo.get_by_id(task.project_id)

        # Permissions check
        if current_user.role == UserRole.EMPLOYEE:
            if task.assigned_to != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update another employee's task.")
        elif current_user.role == UserRole.MANAGER:
            if not project or project.created_by != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update tasks outside your projects.")

        old_status = task.status

        # Enforce prerequisite dependency rule
        if new_status == TaskStatus.COMPLETED:
            prereqs = await self.task_repo.get_dependencies_for_task(task.id)
            incomplete = [p for p in prereqs if p.status != TaskStatus.COMPLETED]
            if incomplete:
                incomplete_desc = ", ".join(f"'{p.task_code}' (status: {p.status.value})" for p in incomplete)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot complete task '{task.task_code}': Required prerequisite task(s) {incomplete_desc} must be COMPLETED first.",
                )
            task.completed_at = utc_now()
        elif old_status == TaskStatus.COMPLETED and new_status != TaskStatus.COMPLETED:
            task.completed_at = None

        task.status = new_status
        if completion_notes is not None:
            task.completion_notes = completion_notes
        await self.task_repo.session.flush()

        # Audit history in same transaction
        await self.history_repo.create(
            task_id=task.id,
            actor_id=current_user.id,
            actor_type=ActorType.HUMAN,
            action="STATUS_CHANGE",
            old_status=old_status.value,
            new_status=new_status.value,
            description=completion_notes or f"Status updated from {old_status.value} to {new_status.value}.",
        )

        # Notify project manager if completed or in review
        if project and current_user.id != project.created_by:
            if new_status in [TaskStatus.COMPLETED, TaskStatus.IN_REVIEW]:
                await self.notification_repo.create_notification(
                    recipient_id=project.created_by,
                    title=f"Task {task.task_code} {new_status.value}",
                    message=f"Task '{task.task_code}: {task.title}' was marked as {new_status.value} by {current_user.full_name}.",
                    notification_type=NotificationType.STATUS_CHANGED,
                )

        return (await self.task_repo.get_by_id_with_deps(task.id)) or task

    async def update_task(self, task_id: uuid.UUID, task_in: TaskUpdate, current_user: User) -> Task:
        task = await self.get_task(task_id, current_user)
        project = await self.project_repo.get_by_id(task.project_id)

        if current_user.role != UserRole.ADMIN and project and project.created_by != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only project managers can edit task details.")

        update_data = task_in.model_dump(exclude_unset=True)
        task = await self.task_repo.update(task, **update_data)
        return (await self.task_repo.get_by_id_with_deps(task.id)) or task

    async def get_task_history(self, task_id: uuid.UUID, current_user: User) -> Sequence[TaskHistory]:
        # Ensure user has access to task first
        await self.get_task(task_id, current_user)
        return await self.history_repo.get_by_task_id(task_id)
