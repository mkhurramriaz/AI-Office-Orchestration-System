"""LangChain and LangGraph workflow for generating validated project plans."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.exceptions import OutputParserException
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.enums import Department, TaskPriority, UserRole
from app.schemas.project_plan import ProjectPlan

logger = logging.getLogger(__name__)


class PlanGenerationError(RuntimeError):
    """Raised when the configured LLM cannot generate structured output."""


class PlanValidationError(RuntimeError):
    """Raised when generated structured output fails plan validation."""


class PlannerState(TypedDict):
    """State passed between the planner's generation and validation nodes."""

    project_brief: str
    plan: ProjectPlan | None


SYSTEM_PROMPT = """You are TaskFlow AI's project planning assistant.
Create a practical project plan from the manager's brief. Return only the
requested structured ProjectPlan. Every task must be actionable and include a
clear title, detailed description, supported required_role, supported
department, priority, and at least one measurable acceptance criterion.
Use only these required_role values: {roles}.
Use only these departments: {departments}.
Use only these priority values: {priorities}.
Give each task a unique, stable task_id. Add dependencies only when logically
necessary and reference task IDs exactly. Never create a dependency cycle.
Do not invent employees, employee names, employee IDs, assignments, or approval
steps. This request generates a plan only; it does not create project records
or tasks in the database."""


def build_structured_planner_model() -> Any:
    """Construct the configured Groq model and bind LangChain structured output."""
    settings = get_settings()
    if settings.DEFAULT_LLM_PROVIDER.lower() != "groq":
        raise PlanGenerationError("The configured planning provider is unavailable.")
    if not settings.GROQ_API_KEY:
        raise PlanGenerationError("The configured planning provider is unavailable.")

    try:
        from langchain_groq import ChatGroq

        model = ChatGroq(
            model=settings.DEFAULT_LLM_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0,
            max_retries=2,
        )
        return model.with_structured_output(ProjectPlan)
    except Exception as exc:
        logger.warning("Could not initialize the structured planner (%s).", type(exc).__name__)
        raise PlanGenerationError("The planning model could not be initialized.") from None


class ProjectPlannerService:
    """Generate project plans with a two-node LangGraph workflow."""

    def __init__(
        self,
        structured_model_factory: Callable[[], Any] = build_structured_planner_model,
    ) -> None:
        self._structured_model_factory = structured_model_factory
        graph = StateGraph(PlannerState)
        graph.add_node("generate_plan", self._generate_plan_node)
        graph.add_node("validate_plan", self._validate_plan_node)
        graph.add_edge(START, "generate_plan")
        graph.add_edge("generate_plan", "validate_plan")
        graph.add_edge("validate_plan", END)
        self._workflow = graph.compile()

    async def create_plan(self, project_brief: str) -> ProjectPlan:
        """Run the graph and return only a fully validated ProjectPlan."""
        if not isinstance(project_brief, str) or not project_brief.strip():
            raise ValueError("Project brief must not be empty.")
        if len(project_brief.strip()) > 10000:
            raise ValueError("Project brief must be 10000 characters or fewer.")

        final_state = await self._workflow.ainvoke(
            {"project_brief": project_brief.strip(), "plan": None}
        )
        plan = final_state.get("plan")
        if not isinstance(plan, ProjectPlan):
            raise PlanValidationError("The planner did not return a validated project plan.")
        return plan

    async def _generate_plan_node(self, state: PlannerState) -> dict[str, ProjectPlan]:
        role_values = ", ".join(role.value for role in UserRole)
        department_values = ", ".join(department.value for department in Department)
        priority_values = ", ".join(priority.value for priority in TaskPriority)
        system_prompt = SYSTEM_PROMPT.format(
            roles=role_values,
            departments=department_values,
            priorities=priority_values,
        )
        try:
            structured_model = self._structured_model_factory()
            result = await structured_model.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=state["project_brief"]),
                ]
            )
        except (ValidationError, OutputParserException):
            raise PlanValidationError("The planning model returned invalid structured output.") from None
        except PlanGenerationError:
            raise
        except Exception as exc:
            logger.warning("Structured plan generation failed (%s).", type(exc).__name__)
            raise PlanGenerationError("The planning service could not generate a plan.") from None

        try:
            plan = result if isinstance(result, ProjectPlan) else ProjectPlan.model_validate(result)
        except ValidationError:
            raise PlanValidationError("The generated project plan failed schema or dependency validation.") from None
        return {"plan": plan}

    async def _validate_plan_node(self, state: PlannerState) -> dict[str, ProjectPlan]:
        plan = state.get("plan")
        try:
            validated_plan = ProjectPlan.model_validate(
                plan.model_dump() if isinstance(plan, ProjectPlan) else plan
            )
        except ValidationError:
            raise PlanValidationError("The generated project plan failed schema or dependency validation.") from None
        return {"plan": validated_plan}
