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

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init
  })
  if (!res.ok) {
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

export function chat(question: string): Promise<ChatResponse> {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ question })
  })
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
