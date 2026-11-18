import React, { useState, useEffect, useCallback } from 'react'
import { api } from './api/client.js'
import IngestionView from './views/IngestionView.jsx'
import StructureView from './views/StructureView.jsx'
import RetrievalInspectorView from './views/RetrievalInspectorView.jsx'
import FinalView from './views/FinalView.jsx'

const VIEWS = [
  { id: 'ingest', label: '1. Document Ingestion' },
  { id: 'structure', label: '2. Document Structure' },
  { id: 'inspector', label: '3. Retrieval Inspector' },
  { id: 'final', label: '4. Final Context / Response' },
]

export default function App() {
  const [view, setView] = useState('ingest')
  const [documents, setDocuments] = useState([])
  const [documentId, setDocumentId] = useState(null)

  // Pipeline run state, shared between the Retrieval Inspector and Final views
  // so "Final" can render whatever the Inspector produced without re-running stages.
  const [pipelineState, setPipelineState] = useState({
    query: '',
    retrieval: null,
    reranking: null,
    context: null,
    generation: null,
  })

  const resetQuery = useCallback(() => {
    setPipelineState({ query: '', retrieval: null, reranking: null, context: null, generation: null })
  }, [])

  const [docsError, setDocsError] = useState(null)

  const refreshDocuments = useCallback(async (selectId = null) => {
    try {
      const list = await api.listDocuments()
      setDocuments(list)
      setDocsError(null)
      setDocumentId((current) => {
        if (selectId && list.some((d) => d.id === selectId)) return selectId
        if (selectId) return selectId
        if (current && list.some((d) => d.id === current)) return current
        return list.length ? list[0].id : null
      })
    } catch (e) {
      setDocsError(e?.message || 'Could not load documents.')
    }
  }, [])

  useEffect(() => {
    refreshDocuments()
  }, [refreshDocuments])

  const document = documents.find((d) => d.id === documentId) || null

  const selectDocument = (id, { inspect = false } = {}) => {
    if (!id || id === documentId) return
    setDocumentId(id)
    resetQuery()
    if (view === 'final') setView('inspector')
    if (inspect) setView('structure')
  }

  const handleIngested = async (doc) => {
    resetQuery()
    setDocumentId(doc.document_id)
    await refreshDocuments(doc.document_id)
    setView('structure')
  }

  const handleDeleteDocument = async (id) => {
    const doc = documents.find((d) => d.id === id)
    const ok = window.confirm(`Remove "${doc?.filename || id}" from the library? Its chunks and embeddings will be deleted.`)
    if (!ok) return
    try {
      await api.deleteDocument(id)
      const wasSelected = id === documentId
      resetQuery()
      await refreshDocuments()
      if (wasSelected) setView('ingest')
    } catch (e) {
      window.alert(`Could not delete document: ${e.message}`)
    }
  }

  return (
    <>
      <header className="app-header">
        <div>
          <h1>RAG Retrieval Visualizer</h1>
          <div className="subtitle">
            {document
              ? `${document.filename} — ${document.parent_count} parents, ${document.child_count} children`
              : documents.length
                ? `${documents.length} document${documents.length === 1 ? '' : 's'} stored`
                : 'No document loaded'}
          </div>
        </div>
        <nav className="nav">
          {documents.length > 0 && (
            <select
              className="doc-select"
              value={documentId || ''}
              onChange={(e) => selectDocument(e.target.value)}
              aria-label="Select working document"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} — {d.parent_count} parents
                </option>
              ))}
            </select>
          )}
          {VIEWS.map((v) => (
            <button
              key={v.id}
              className={view === v.id ? 'active' : ''}
              disabled={v.id !== 'ingest' && !document}
              onClick={() => setView(v.id)}
            >
              {v.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="content">
        {docsError && view === 'ingest' && (
          <div className="error-box" style={{ marginBottom: 16 }}>
            <span className="stage-tag">documents</span>
            {docsError}
          </div>
        )}
        {view === 'ingest' && (
          <IngestionView
            documents={documents}
            selectedDocumentId={documentId}
            onSelectDocument={(id) => selectDocument(id, { inspect: true })}
            onIngested={handleIngested}
            onLibraryChange={() => refreshDocuments()}
            onDeleteDocument={handleDeleteDocument}
          />
        )}

        {view === 'structure' && document && (
          <StructureView documentId={document.id} />
        )}

        {view === 'inspector' && document && (
          <RetrievalInspectorView
            document={document}
            documentId={document.id}
            pipelineState={pipelineState}
            setPipelineState={setPipelineState}
            onResetQuery={resetQuery}
            onDone={() => setView('final')}
          />
        )}

        {view === 'final' && document && (
          <FinalView
            document={document}
            pipelineState={pipelineState}
            onNewQuery={() => {
              resetQuery()
              setView('inspector')
            }}
          />
        )}
      </div>
    </>
  )
}
