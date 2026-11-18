import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api/client.js'
import Markdown from '../components/Markdown.jsx'

export default function RetrievalInspectorView({ document, documentId, pipelineState, setPipelineState, onResetQuery, onDone }) {
  const [queryInput, setQueryInput] = useState(pipelineState.query || '')
  const [scope, setScope] = useState('selected') // 'selected' | 'all'
  const [loadingStage, setLoadingStage] = useState(null)
  const [error, setError] = useState(null)

  const { retrieval, reranking, context, generation } = pipelineState

  // If the working document changed (header dropdown), reset everything —
  // but ignore the initial mount / remount (navigating back to this view
  // must keep the shared pipeline state intact).
  const mountedDocId = useRef(documentId)
  useEffect(() => {
    if (mountedDocId.current === documentId) return
    mountedDocId.current = documentId
    setQueryInput('')
    setScope('selected')
    setError(null)
    onResetQuery()
  }, [documentId, onResetQuery])

  const queryChanged = pipelineState.query && queryInput.trim() !== pipelineState.query
  const searchingAll = scope === 'all'

  const setScopeAndClear = (next) => {
    if (next === scope) return
    setScope(next)
    setError(null)
    setPipelineState((s) => ({ ...s, retrieval: null, reranking: null, context: null, generation: null }))
  }

  const runRetrieve = async () => {
    if (!queryInput.trim()) return
    setError(null)
    setLoadingStage('retrieve')
    try {
      const data = await api.retrieve(searchingAll ? null : documentId, queryInput, 5)
      setPipelineState((s) => ({ ...s, query: queryInput, retrieval: data, reranking: null, context: null, generation: null }))
    } catch (e) {
      setError(e)
    } finally {
      setLoadingStage(null)
    }
  }

  const runRerank = async () => {
    setError(null)
    setLoadingStage('rerank')
    try {
      const data = await api.rerank(pipelineState.query, retrieval.candidates, 3)
      setPipelineState((s) => ({ ...s, reranking: data, context: null, generation: null }))
    } catch (e) {
      setError(e)
    } finally {
      setLoadingStage(null)
    }
  }

  const runBuildContext = async () => {
    setError(null)
    setLoadingStage('build_context')
    try {
      const data = await api.buildContext(searchingAll ? null : documentId, reranking.after)
      setPipelineState((s) => ({ ...s, context: data, generation: null }))
    } catch (e) {
      setError(e)
    } finally {
      setLoadingStage(null)
    }
  }

  const runGenerate = async () => {
    setError(null)
    setLoadingStage('generate')
    try {
      const data = await api.generate(pipelineState.query, context.assembled_context)
      setPipelineState((s) => ({ ...s, generation: data }))
    } catch (e) {
      setError(e)
    } finally {
      setLoadingStage(null)
    }
  }

  const runAll = async () => {
    if (!queryInput.trim()) return
    setError(null)
    setLoadingStage('all')
    try {
      const data = await api.queryFull(searchingAll ? null : documentId, queryInput, 5, 3)
      setPipelineState({
        query: queryInput,
        retrieval: data.retrieval,
        reranking: data.reranking,
        context: data.context,
        generation: data.generation,
      })
    } catch (e) {
      setError(e)
    } finally {
      setLoadingStage(null)
    }
  }

  const handleReset = () => {
    setQueryInput('')
    onResetQuery()
    setError(null)
  }

  return (
    <div>
      <div className="panel">
        <h2>Retrieval Inspector</h2>
        <div className="scope-toggle" style={{ marginBottom: 12 }}>
          <span className="scope-label">Search scope:</span>
          <button className={scope === 'selected' ? 'active' : ''} onClick={() => setScopeAndClear('selected')}>
            {document.filename}
          </button>
          <button className={scope === 'all' ? 'active' : ''} onClick={() => setScopeAndClear('all')}>
            All documents
          </button>
        </div>
        <div className="query-row">
          <input
            type="text"
            placeholder="Ask a question about the document..."
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runRetrieve()}
          />
          <button className="secondary" onClick={handleReset}>
            Reset Query
          </button>
        </div>

        {queryChanged && (
          <div className="warning-box">
            Query changed since the results below were produced — re-run Retrieve (or Run All Stages) to refresh them.
          </div>
        )}

        <div className="stage-actions" style={{ marginTop: 20 }}>
          <StageButton label="1. Retrieve" onClick={runRetrieve} active={loadingStage === 'retrieve'} done={!!retrieval} disabled={!queryInput.trim() || loadingStage} />
          <StageButton label="2. Rerank" onClick={runRerank} active={loadingStage === 'rerank'} done={!!reranking} disabled={!retrieval || loadingStage} />
          <StageButton label="3. Build Context" onClick={runBuildContext} active={loadingStage === 'build_context'} done={!!context} disabled={!reranking || loadingStage} />
          <StageButton label="4. Generate Answer" onClick={runGenerate} active={loadingStage === 'generate'} done={!!generation} disabled={!context || loadingStage} />
          <StageButton label="Run All Stages" onClick={runAll} active={loadingStage === 'all'} done={!!generation && !!context && !!reranking && !!retrieval} disabled={!queryInput.trim() || loadingStage} />
        </div>

        {error && (
          <div className="error-box" style={{ marginTop: 16 }}>
            <span className="stage-tag">{error.stage}</span>
            {error.message}
          </div>
        )}
      </div>

      {retrieval && (
        <div className="panel">
          <h3>Vector Retrieval — Top {retrieval.top_k} Candidates{searchingAll ? ' (across all documents)' : ''}</h3>
          <p style={{ color: 'var(--text-dim)', fontSize: 14, marginTop: -8 }}>
            Query: "{retrieval.query}"
          </p>
          {retrieval.candidates.map((c) => (
            <div className="chunk-card" key={c.child_id}>
              <div className="meta">
                <span className="rank-badge">#{c.rank}</span>
                <span className="score">similarity: {c.similarity}</span>
              </div>
              <div className="text-preview">{c.text}</div>
              <div className="source-line">{c.document_filename}{c.page_number ? ` · page ${c.page_number}` : ''}</div>
            </div>
          ))}
        </div>
      )}

      {reranking && (
        <div className="panel">
          <h3>Before / After Reranking</h3>
          <p style={{ color: 'var(--text-dim)', fontSize: 13, marginTop: -8 }}>
            Note: similarity and rerank scores are on different scales — compare rank movement, not the raw numbers.
          </p>
          <div className="compare-grid" style={{ marginTop: 16 }}>
            <div>
              <h3>Vector Result</h3>
              {reranking.before.map((c) => (
                <div className="chunk-card" key={c.child_id}>
                  <div className="meta">
                    <span className="rank-badge">#{c.vector_rank}</span>
                    <span className="score">sim: {c.similarity}</span>
                  </div>
                  <div className="text-preview">{c.text}</div>
                  <div className="source-line">{c.document_filename}</div>
                </div>
              ))}
            </div>
            <div>
              <h3>Reranked Result (top {reranking.after.length})</h3>
              {reranking.after_full.map((c) => (
                <div className="chunk-card" key={c.child_id} style={{ opacity: c.rerank_rank <= reranking.after.length ? 1 : 0.4 }}>
                  <div className="meta">
                    <span className="rank-badge">#{c.rerank_rank}</span>
                    <span className="score">rerank: {c.rerank_score.toFixed(3)}</span>
                    <MovementTag movement={c.movement} />
                  </div>
                  <div className="text-preview">{c.text}</div>
                  <div className="source-line">{c.document_filename}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {context && (
        <div className="panel">
          <h3>Selected Children → Parent Context</h3>
          <p style={{ color: 'var(--text-dim)', fontSize: 14 }}>
            {context.deduplicated_from} selected children resolved to {context.unique_parents} unique parent
            {context.unique_parents === 1 ? '' : 's'} (duplicates collapsed).
          </p>
          {context.parents_used.map((p) => (
            <div className="context-block" key={p.parent_id}>
              <div className="source-tag">{p.source}{p.page_number ? ` · page ${p.page_number}` : ''}</div>
              {p.text}
            </div>
          ))}
        </div>
      )}

      {generation && (
        <div className="panel">
          <h3>Final Answer</h3>
          <div className="answer-box"><Markdown text={generation.answer} /></div>
          <div style={{ marginTop: 16 }}>
            <button className="primary" onClick={onDone}>
              View Full Pipeline Summary
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function StageButton({ label, onClick, active, done, disabled }) {
  return (
    <button className={`${done ? 'secondary' : 'primary'} ${active ? 'active' : ''}`} onClick={onClick} disabled={disabled}>
      <span className={`stage-dot ${done ? 'done' : active ? 'active' : 'pending'}`} style={{ display: 'inline-flex', marginRight: 8, verticalAlign: 'middle' }}>
        {done ? '✓' : active ? '…' : ''}
      </span>
      {label}
    </button>
  )
}

function MovementTag({ movement }) {
  if (movement > 0) return <span className="movement-up">↑ {movement}</span>
  if (movement < 0) return <span className="movement-down">↓ {Math.abs(movement)}</span>
  return <span className="movement-same">—</span>
}
