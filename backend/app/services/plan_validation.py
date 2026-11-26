"""Validation helpers for generated project task dependency graphs."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from typing import Any


def validate_dependency_graph(tasks: Sequence[Any]) -> None:
    """Validate task IDs and dependency edges in O(V + E) time.

    Tasks may be Pydantic models or mappings containing ``task_id`` and
    ``dependencies``. Edges point from each prerequisite to the task that
    depends on it. Kahn's algorithm detects cycles.
    """
    task_ids: list[str] = []
    dependencies_by_task: dict[str, list[str]] = {}

    for task in tasks:
        if isinstance(task, Mapping):
            task_id = task.get("task_id")
            dependencies = task.get("dependencies", [])
        else:
            task_id = getattr(task, "task_id", None)
            dependencies = getattr(task, "dependencies", [])

        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("Every task must have a non-empty task_id.")
        task_ids.append(task_id)
        dependencies_by_task[task_id] = list(dependencies or [])

    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Task IDs must be unique.")

    known_ids = set(task_ids)
    outgoing: dict[str, list[str]] = defaultdict(list)
    in_degree = {task_id: 0 for task_id in task_ids}

    for task_id, dependencies in dependencies_by_task.items():
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(f"Task '{task_id}' contains duplicate dependencies.")
        for dependency in dependencies:
            if dependency == task_id:
                raise ValueError(f"Task '{task_id}' cannot depend on itself.")
            if dependency not in known_ids:
                raise ValueError(
                    f"Task '{task_id}' references missing dependency '{dependency}'."
                )
            outgoing[dependency].append(task_id)
            in_degree[task_id] += 1

    ready = deque(task_id for task_id, count in in_degree.items() if count == 0)
    visited_count = 0
    while ready:
        task_id = ready.popleft()
        visited_count += 1
        for dependent_id in outgoing[task_id]:
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                ready.append(dependent_id)

    if visited_count != len(task_ids):
        raise ValueError("Task dependencies contain a circular dependency.")
