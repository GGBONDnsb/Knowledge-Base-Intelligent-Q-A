export interface Citation {
  doc_id: string
  title: string
  heading: string
  content: string
  permission: string
  score: number
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
  refused: boolean
}

export interface DocumentItem {
  doc_id: string
  title: string
  category: string
  permission: string
  owner: string
  status: string
  filename: string
  chunk_count: number
}

export interface Stats {
  documents: number
  chunks: number
  question_count: number
  categories: Record<string, number>
}

export interface AgentPendingAction {
  action_id: string
  tool: string
  summary: string
  payload: Record<string, unknown>
  created_at: string
}

export interface AgentChatResponse {
  session_id: string
  answer: string
  citations: Citation[]
  pending_action: AgentPendingAction | null
  steps: number
}

export interface AgentActionResponse {
  action_id: string
  status: 'confirmed' | 'cancelled'
  request_id?: string
  message: string
}

export interface AgentEmployee {
  employee_id: string
  name: string
  department: string
  position: string
  role: 'employee' | 'manager'
  manager_id: string
  department_head_id: string
}

export interface AgentLeaveRequest {
  request_id: string
  employee_id: string
  employee_name: string
  department: string
  leave_type: string
  start_date: string
  end_date: string
  days: number
  reason: string
  status: '待审批' | '已批准' | '已拒绝' | '已取消'
  approver_id: string
  submitted_at: string
}

export interface AuthUser {
  employee_id: string
  username: string
  name: string
  department: string
  position: string
  role: 'employee' | 'manager' | 'admin'
  manager_id: string
  department_head_id: string
}

export interface LoginResponse {
  token: string
  expires_at: string
  user: AuthUser
}

export interface AgentActionEvent {
  event_id: string
  event_type:
    | 'created'
    | 'confirmed'
    | 'executed'
    | 'failed'
    | 'cancelled'
    | 'expired'
  actor_employee_id: string
  actor_name: string
  detail: Record<string, unknown>
  created_at: string | null
}

export interface AgentActionAuditItem {
  action_id: string
  session_id: string
  actor_employee_id: string
  actor_name: string
  tool_name: string
  summary: string
  status: string
  created_at: string | null
  expires_at: string | null
  confirmed_at: string | null
  cancelled_at: string | null
  executed_at: string | null
  result: Record<string, unknown>
  error_message: string
  event_count: number
}

export interface AgentActionAuditDetail extends AgentActionAuditItem {
  payload: Record<string, unknown>
  events: AgentActionEvent[]
  related_request: Record<string, unknown> | null
}

const TOKEN_KEY = 'knowledge_agent_token'

export function getAuthToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function setAuthToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getAuthToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await fetch(url, {
    ...init,
    headers
  })
  if (!res.ok) {
    if (res.status === 401) {
      clearAuthToken()
      window.dispatchEvent(new Event('auth:unauthorized'))
    }
    let detail = `请求失败: ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) {
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      // keep default message
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
}

export function getMe(): Promise<AuthUser> {
  return request('/api/auth/me')
}

export function logout(): Promise<{ logged_out: boolean }> {
  return request('/api/auth/logout', { method: 'POST' })
}

export function chat(question: string, role: string = 'employee'): Promise<ChatResponse> {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ question, role })
  })
}

export function agentChat(
  message: string,
  sessionId?: string
): Promise<AgentChatResponse> {
  return request('/api/agent/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId ?? null
    })
  })
}

export function confirmAgentAction(actionId: string): Promise<AgentActionResponse> {
  return request(`/api/agent/actions/${encodeURIComponent(actionId)}/confirm`, {
    method: 'POST'
  })
}

export function cancelAgentAction(actionId: string): Promise<AgentActionResponse> {
  return request(`/api/agent/actions/${encodeURIComponent(actionId)}`, {
    method: 'DELETE'
  })
}

export function listAgentActions(
  status?: string,
  toolName?: string
): Promise<AgentActionAuditItem[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (toolName) params.set('tool_name', toolName)
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return request(`/api/agent/actions${suffix}`)
}

export function getAgentAction(
  actionId: string
): Promise<AgentActionAuditDetail> {
  return request(`/api/agent/actions/${encodeURIComponent(actionId)}`)
}

export function resetDemoData(): Promise<{
  employees: number
  balances: number
  leave_requests: number
}> {
  return request('/api/agent/demo/reset', { method: 'POST' })
}

export function listAgentEmployees(): Promise<AgentEmployee[]> {
  return request('/api/agent/employees')
}

export function listMyLeaveRequests(
  status?: string
): Promise<AgentLeaveRequest[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return request(`/api/agent/leave-requests${suffix}`)
}

export function listPendingApprovals(): Promise<AgentLeaveRequest[]> {
  return request('/api/agent/approvals')
}

export function prepareApproval(
  requestId: string
): Promise<AgentPendingAction> {
  return request(
    `/api/agent/leave-requests/${encodeURIComponent(requestId)}/approve`,
    { method: 'POST' }
  )
}

export function prepareRejection(
  requestId: string,
  reason: string
): Promise<AgentPendingAction> {
  return request(
    `/api/agent/leave-requests/${encodeURIComponent(requestId)}/reject`,
    {
      method: 'POST',
      body: JSON.stringify({ reason })
    }
  )
}

export function listDocuments(): Promise<DocumentItem[]> {
  return request('/api/documents')
}

export function uploadDocument(file: File): Promise<{ doc_id: string; title: string; chunk_count: number }> {
  const form = new FormData()
  form.append('file', file)
  return fetch('/api/documents/upload', { method: 'POST', body: form }).then(async (res) => {
    if (!res.ok) {
      let detail = `上传失败: ${res.status}`
      try {
        const body = await res.json()
        if (body?.detail) detail = body.detail
      } catch {
        // keep default message
      }
      throw new Error(detail)
    }
    return res.json()
  })
}

export function deleteDocument(docId: string): Promise<{ deleted: boolean }> {
  return request(`/api/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' })
}

export function reindexDocuments(): Promise<{ documents: number; chunks: number }> {
  return request('/api/documents/reindex', { method: 'POST' })
}

export function getStats(): Promise<Stats> {
  return request('/api/stats')
}
