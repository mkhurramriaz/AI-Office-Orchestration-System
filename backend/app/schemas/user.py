import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Department, ProfessionalRole, UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    department: Department = Department.OTHER
    job_title: str | None = Field(None, max_length=255)
    professional_role: ProfessionalRole | None = None


class UserRegister(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    # Public registration can choose EMPLOYEE or MANAGER (defaults to EMPLOYEE), but NEVER ADMIN
    role: UserRole = Field(default=UserRole.EMPLOYEE, description="Desired role: EMPLOYEE or MANAGER. Cannot register as ADMIN.")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.EMPLOYEE
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    department: Department | None = None
    job_title: str | None = None
    professional_role: ProfessionalRole | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=128)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
