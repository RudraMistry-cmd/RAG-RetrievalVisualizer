const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function getSessionId() {
  const key = 'rag_session_id'
  try {
    let id = localStorage.getItem(key)
    if (!id) {
      id = (crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`)
      localStorage.setItem(key, id)
    }
    return id
  } catch {
    return 'anonymous'
  }
}

class ApiError extends Error {
  constructor(stage, message, status) {
    super(message)
    this.stage = stage
    this.status = status
  }
}

async function request(path, options = {}) {
  let resp
  try {
    const isForm = options.body instanceof FormData
    const headers = {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      'ngrok-skip-browser-warning': 'true',
      'X-Session-Id': getSessionId(),
      ...(options.headers || {}),
    }
    resp = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers,
    })
  } catch (e) {
    throw new ApiError('network', `Could not reach backend at ${BASE_URL}. Is it running?`, 0)
  }

  if (!resp.ok) {
    let detail
    try {
      const data = await resp.json()
      detail = data.detail
    } catch {
      detail = { stage: 'unknown', message: resp.statusText }
    }
    if (typeof detail === 'string') {
      throw new ApiError('unknown', detail, resp.status)
    }
    throw new ApiError(detail?.stage || 'unknown', detail?.message || 'Request failed', resp.status)
  }

  return resp.json()
}

export const api = {
  health: () => request('/api/health'),

  ingest: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/ingest', { method: 'POST', body: form })
  },

  listDocuments: () => request('/api/documents'),

  deleteDocument: (documentId) => request(`/api/documents/${documentId}`, { method: 'DELETE' }),

  documentStructure: (documentId) => request(`/api/documents/${documentId}/structure`),

  extraction: (documentId) => request(`/api/documents/${documentId}/extraction`),

  retrieve: (documentId, query, topK) =>
    request('/api/retrieve', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, query, top_k: topK }),
    }),

  rerank: (query, candidates, topN) =>
    request('/api/rerank', {
      method: 'POST',
      body: JSON.stringify({ query, candidates, top_n: topN }),
    }),

  buildContext: (documentId, selectedChildren) =>
    request('/api/build-context', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, selected_children: selectedChildren }),
    }),

  generate: (question, context) =>
    request('/api/generate', {
      method: 'POST',
      body: JSON.stringify({ question, context }),
    }),

  queryFull: (documentId, query, topK, topN) =>
    request('/api/query/full', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, query, top_k: topK, top_n: topN }),
    }),
}

export { ApiError }
