import { api } from './client'
import type { ChatResponse, PaginatedResponse, Project, Task, TaskStatus, WorkflowExecution } from '../types/api'

export const workspaceApi = {
  projects: async () => (await api.get<PaginatedResponse<Project>>('/projects', { params: { page: 1, size: 100 } })).data,
  project: async (id: string) => (await api.get<Project>(`/projects/${id}`)).data,
  tasks: async (params?: { project_id?: string }) => (await api.get<PaginatedResponse<Task>>('/tasks', { params: { page: 1, size: 100, ...params } })).data,
  task: async (id: string) => (await api.get<Task>(`/tasks/${id}`)).data,
  updateTaskStatus: async (id: string, taskStatus: TaskStatus) =>
    (await api.post<Task>(`/tasks/${id}/status`, { status: taskStatus })).data,
  chat: async (question: string, conversationId?: string) =>
    (await api.post<ChatResponse>('/ai/chat', { question, ...(conversationId ? { conversation_id: conversationId } : {}) })).data,
  startWorkflow: async (project_brief: string) => (await api.post<WorkflowExecution>('/ai/workflows', { project_brief })).data,
  workflow: async (id: string) => (await api.get<WorkflowExecution>(`/ai/workflows/${id}`)).data,
  decideWorkflow: async (id: string, decision: 'APPROVE' | 'REJECT') =>
    (await api.post<WorkflowExecution>(`/ai/workflows/${id}/decision`, { decision })).data,
}

const WORKFLOW_IDS_PREFIX = 'taskflow.workflow_ids.'
export function getTrackedWorkflowIds(userId: string): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(`${WORKFLOW_IDS_PREFIX}${userId}`) ?? '[]')
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === 'string') : []
  } catch { return [] }
}

export function trackWorkflow(userId: string, workflowId: string) {
  const ids = getTrackedWorkflowIds(userId)
  if (!ids.includes(workflowId)) localStorage.setItem(`${WORKFLOW_IDS_PREFIX}${userId}`, JSON.stringify([workflowId, ...ids].slice(0, 50)))
}
