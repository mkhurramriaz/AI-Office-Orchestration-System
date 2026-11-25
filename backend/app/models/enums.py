from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class Department(str, Enum):
    WEB = "WEB"
    SEO = "SEO"
    MARKETING = "MARKETING"
    QA = "QA"
    AI = "AI"
    DESIGN = "DESIGN"
    OPERATIONS = "OPERATIONS"
    OTHER = "OTHER"


class ProjectStatus(str, Enum):
    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ActorType(str, Enum):
    HUMAN = "HUMAN"
    AI = "AI"


class NotificationType(str, Enum):
    TASK_ASSIGNED = "TASK_ASSIGNED"
    STATUS_CHANGED = "STATUS_CHANGED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    PROJECT_UPDATE = "PROJECT_UPDATE"
    SYSTEM = "SYSTEM"


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    INTERRUPTED = "INTERRUPTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
