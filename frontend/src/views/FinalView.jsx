import React from 'react'

export default function FinalView({ document, pipelineState, onNewQuery }) {
  const { query, retrieval, reranking, context, generation } = pipelineState

  if (!generation) {
    return (
      <div className="panel empty-state">
        <p>No completed query yet. Run a query through the Retrieval Inspector first.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="panel">
        <h2>Full Pipeline Summary</h2>
        <p style={{ color: 'var(--text-dim)' }}>
          Document: <strong>{document.filename}</strong> · Query: "{query}"
        </p>
      </div>

      <div className="panel">
        <h3>Pipeline Flow</h3>
        <FlowStep label={`Vector retrieval: ${retrieval.candidates.length} candidates`} />
        <FlowStep label={`Reranking: top ${reranking.after.length} selected (from ${reranking.before.length})`} />
        <FlowStep label={`Context: ${context.unique_parents} unique parent chunk${context.unique_parents === 1 ? '' : 's'} assembled`} />
        <FlowStep label="LLM generation: complete" />
      </div>

      <div className="panel">
        <h3>Selected Children</h3>
        {reranking.after.map((c) => (
          <div className="chunk-card" key={c.child_id}>
            <div className="meta">
              <span className="rank-badge">#{c.rerank_rank}</span>
              <span className="score">rerank: {c.rerank_score.toFixed(3)}</span>
              <span style={{ color: 'var(--text-dim)' }}>(was vector rank #{c.vector_rank})</span>
            </div>
            <div className="text-preview">{c.text}</div>
            <div className="source-line">{c.document_filename}</div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Final Context Sent to LLM</h3>
        {context.parents_used.map((p) => (
          <div className="context-block" key={p.parent_id}>
            <div className="source-tag">{p.source}{p.page_number ? ` · page ${p.page_number}` : ''}</div>
            {p.text}
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Answer</h3>
        <div className="answer-box">{generation.answer}</div>
        <p style={{ color: 'var(--text-dim)', fontSize: 13, marginTop: 12 }}>
          Model: {generation.model}
        </p>
      </div>

      <button className="primary" onClick={onNewQuery}>
        Ask Another Question
      </button>
    </div>
  )
}

function FlowStep({ label }) {
  return (
    <div className="stage-row">
      <span className="stage-dot done">✓</span>
      <span>{label}</span>
    </div>
  )
}
