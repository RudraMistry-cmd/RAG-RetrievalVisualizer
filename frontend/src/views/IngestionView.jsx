import React, { useState, useRef } from 'react'
import { api } from '../api/client.js'

export default function IngestionView({ documents, selectedDocumentId, onSelectDocument, onIngested, onLibraryChange, onDeleteDocument }) {
  const [status, setStatus] = useState('idle') // idle | processing | done | error
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const fileInput = useRef(null)

  const handleFile = (e) => {
    const file = e.target.files[0]
    e.target.value = '' // allow re-selecting the same file later
    if (!file) return
    setStatus('processing')
    setError(null)
    setResult(null)
    setProcessingAsync(file)
  }

  const setProcessingAsync = async (file) => {
    try {
      const data = await api.ingest(file)
      setResult(data)
      setStatus('done')
      onLibraryChange()
    } catch (e) {
      setError(e)
      setStatus('error')
    }
  }

  return (
    <div>
      <div className="panel">
        <h2>Document Ingestion</h2>
        <p style={{ color: 'var(--text-dim)' }}>
          Upload one or more documents. Each is split into parent chunks (larger, for context) and
          child chunks (smaller, for precise search), then embedded and stored in the library below.
        </p>

        <div
          style={{
            border: '2px dashed var(--border)',
            borderRadius: '10px',
            padding: '40px',
            textAlign: 'center',
            marginTop: '16px',
            marginBottom: '16px',
          }}
        >
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.txt,.md"
            style={{ display: 'none' }}
            onChange={handleFile}
          />
          <button className="primary" onClick={() => fileInput.current?.click()} disabled={status === 'processing'}>
            {status === 'processing' ? 'Processing…' : 'Choose File (.pdf, .txt, .md)'}
          </button>
        </div>

        {status === 'processing' && (
          <div className="stage-row">
            <span className="stage-dot active">…</span>
            <span className="loading-text">Extracting text → chunking → embedding → storing…</span>
          </div>
        )}

        {status === 'error' && (
          <div className="error-box">
            <span className="stage-tag">{error.stage}</span>
            {error.message}
          </div>
        )}

        {status === 'done' && result && (
          <div>
            <h3 style={{ marginTop: 24 }}>Document Processed ✓</h3>
            <div style={{ display: 'flex', gap: 24, marginBottom: 20, flexWrap: 'wrap' }}>
              <Stat label="Pages" value={result.pages} />
              <Stat label="Parents" value={result.parent_count} />
              <Stat label="Children" value={result.child_count} />
              <Stat label="Embeddings" value={result.embedding_count} />
              {result.pages_ocr > 0 && <Stat label="OCR'd Pages" value={result.pages_ocr} />}
            </div>
            <p style={{ color: 'var(--text-dim)', fontSize: 14 }}>
              Embedding model: <code>{result.embedding_model}</code>
            </p>
            <button className="primary" onClick={() => onIngested(result)}>
              View Document Structure →
            </button>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Document Library</h3>
        <p style={{ color: 'var(--text-dim)', fontSize: 14, marginTop: -6 }}>
          {documents.length
            ? 'All ingested documents. Select one to make it the working document for the structure and retrieval views.'
            : 'No documents stored yet — upload one above.'}
        </p>
        <div className="doc-list">
          {documents.map((d) => {
            const active = d.id === selectedDocumentId
            return (
              <div key={d.id} className={`doc-row ${active ? 'selected' : ''}`}>
                <div className="doc-info">
                  <strong>{d.filename}</strong>
                  <div className="doc-meta">
                    {d.parent_count} parents · {d.child_count} children
                  </div>
                </div>
                <div className="doc-actions">
                  <button className="secondary" disabled={active} onClick={() => onSelectDocument(d.id)}>
                    {active ? 'Active' : 'Select & Inspect →'}
                  </button>
                  <button className="secondary danger" onClick={() => onDeleteDocument(d.id)} aria-label={`Remove ${d.filename}`}>
                    Remove
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: 13, color: 'var(--text-dim)', textTransform: 'uppercase' }}>{label}</div>
    </div>
  )
}
