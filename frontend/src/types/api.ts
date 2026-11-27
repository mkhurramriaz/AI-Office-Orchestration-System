export type UserRole = 'ADMIN' | 'MANAGER' | 'EMPLOYEE'
export type Department = 'WEB' | 'SEO' | 'MARKETING' | 'QA' | 'AI' | 'DESIGN' | 'OPERATIONS' | 'OTHER'
export type ProfessionalRole =
  | 'FRONTEND_DEVELOPER' | 'BACKEND_DEVELOPER' | 'FULL_STACK_DEVELOPER' | 'AI_ENGINEER'
  | 'DATA_ENGINEER' | 'DEVOPS_ENGINEER' | 'QA_ENGINEER' | 'SEO_SPECIALIST'
  | 'DIGITAL_MARKETER' | 'UI_UX_DESIGNER' | 'PROJECT_MANAGER' | 'BUSINESS_ANALYST'
  | 'CONTENT_WRITER' | 'OPERATIONS_SPECIALIST'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  department: Department
  job_title: string | null
  professional_role: ProfessionalRole | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AdminOverview {
  total_users: number
  active_users: number
  inactive_users: number
  users_by_account_role: Record<UserRole, number>
  employees_by_department: Partial<Record<Department, number>>
  employees_by_professional_role: Partial<Record<ProfessionalRole, number>>
  total_projects: number
  projects_by_status: Partial<Record<ProjectStatus, number>>
  total_tasks: number
  tasks_by_status: Partial<Record<TaskStatus, number>>
}

export interface Notification {
  id: string
  recipient_id: string
  title: string
  message: string
  notification_type: 'TASK_ASSIGNED' | 'STATUS_CHANGED' | 'REVIEW_REQUESTED' | 'PROJECT_UPDATE' | 'SYSTEM'
  is_read: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface LoginRequest { email: string; password: string }
export interface RegisterRequest {
  email: string
  full_name: string
  password: string
  role: Exclude<UserRole, 'ADMIN'>
  department: Department
  job_title?: string
  professional_role?: ProfessionalRole
}

export type ProjectStatus = 'DRAFT' | 'PLANNING' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED'
export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'BLOCKED' | 'IN_REVIEW' | 'COMPLETED' | 'CANCELLED'
export type TaskPriority = 'HIGH' | 'MEDIUM' | 'LOW'
export type WorkflowStatus = 'PENDING' | 'RUNNING' | 'INTERRUPTED' | 'COMPLETED' | 'FAILED' | 'REJECTED'

export interface PaginatedResponse<T> { items: T[]; total: number; page: number; size: number; pages: number }
export interface Project {
  id: string
  project_name: string
  description: string | null
  original_brief: string | null
  status: ProjectStatus
  created_by: string
  start_date: string | null
  deadline: string | null
  created_at: string
  updated_at: string
  task_count: number
}
export interface Task {
  id: string
  project_id: string
  task_code: string
  title: string
  description: string | null
  department: Department
  required_role: string | null
  priority: TaskPriority
  status: TaskStatus
  assigned_to: string | null
  assigned_by: string | null
  acceptance_criteria: string | null
  completion_notes: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  dependencies: string[]
}
export interface PlannedTask {
  task_id: string
  title: string
  description: string
  required_role: ProfessionalRole
  department: Department
  priority: TaskPriority
  dependencies: string[]
  acceptance_criteria: string[]
}
export interface ProjectPlan { project_name: string; project_description: string; tasks: PlannedTask[] }
export interface AssignmentRecommendation {
  task_id: string
  task_title: string
  employee_id: string
  employee_name: string
  department: Department
  required_role: ProfessionalRole
  current_workload: number
  projected_workload: number
  reason: string
}
export interface UnassignedTask { task_id: string; task_title: string; reason: string }
export interface AssignmentResult {
  project_name: string
  assignments: AssignmentRecommendation[]
  unassigned_tasks: UnassignedTask[]
  is_fully_assigned: boolean
}
export interface WorkflowOutput {
  plan?: ProjectPlan
  recommendations?: AssignmentResult
  project_id?: string
  task_ids?: Record<string, string>
  tasks?: Task[]
}
export interface WorkflowExecution {
  id: string
  project_id: string | null
  initiated_by: string
  status: WorkflowStatus
  thread_id: string
  input_data: { project_brief?: string; [key: string]: unknown }
  output_data: WorkflowOutput | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}
export interface ChatSource { source: string; content: string; metadata: Record<string, unknown>; relevance_score: number }
export interface ChatResponse { conversation_id: string; answer: string; sources: ChatSource[] }
