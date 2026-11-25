---
title: Project Management Guidelines
author: Operations Team
tags: [project-management, process, guidelines]
version: "2.1"
---

# Project Management Guidelines

## 1. Purpose

This document establishes the standard process for initiating, planning, executing,
monitoring, and closing projects at TaskFlow AI.

## 2. Project Initiation

A new project is initiated by a manager submitting a **Project Brief** that includes:
- Project name and description.
- Business objective and expected outcomes.
- Target completion date.
- Assigned department and team members.
- Budget estimate (if applicable).

The Project Brief must be reviewed and approved by a senior manager or department head
before work begins.

## 3. Task Decomposition

Once a project is approved, the project manager decomposes the work into tasks:

- Each task must have a clear title and description.
- Tasks should be scoped to fit within one to five working days.
- Dependencies between tasks must be explicitly stated.
- Each task must be assigned to a named employee.
- Estimated effort (in hours) should be provided for each task.

## 4. Task Priority Levels

| Priority | Description |
|----------|-------------|
| CRITICAL | Blocking other tasks or the entire project. |
| HIGH | Important and time-sensitive. |
| MEDIUM | Standard priority (default). |
| LOW | Nice-to-have; can be deferred. |

## 5. Task Status Workflow

Tasks follow a defined status lifecycle:

```
TODO → IN_PROGRESS → IN_REVIEW → COMPLETED
                 ↘ BLOCKED
```

- **TODO**: Task is defined and assigned but work has not started.
- **IN_PROGRESS**: The employee is actively working on the task.
- **BLOCKED**: The task cannot proceed due to an unresolved dependency or issue.
- **IN_REVIEW**: The employee has submitted the task for manager review.
- **COMPLETED**: The manager has approved the task submission.

## 6. Approval Workflow

When an employee marks a task as IN_REVIEW, the assigned manager receives
a notification. The manager may:

1. **Approve** — mark the task as COMPLETED.
2. **Request Revision** — revert the task to IN_PROGRESS with feedback.

## 7. Project Completion

A project is marked as COMPLETED when all its tasks are in COMPLETED status.
The project manager must submit a Project Closure Report summarising:
- Outcomes achieved.
- Lessons learned.
- Any outstanding risks or follow-up items.

## 8. AI-Assisted Planning

TaskFlow AI provides an AI Co-Pilot that can:
- Decompose a natural-language project brief into actionable tasks.
- Suggest suitable employees based on role, skills, and workload.
- Identify potential task dependencies.
- Generate a project timeline.

Managers should review and approve all AI-generated plans before execution.

## 9. Reporting

Weekly project status reports are automatically generated and sent to:
- The project manager.
- All assigned employees.
- Senior management (for projects marked HIGH priority or above).

## 10. Document Storage

All project-related documents must be uploaded to the company document repository.
Documents are automatically indexed by the AI Co-Pilot for context-aware assistance.
