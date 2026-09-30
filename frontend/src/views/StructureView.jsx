import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'

export default function StructureView({ documentId }) {
  const [structure, setStructure] = useState(null)
  const [extraction, setExtraction] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null) // { type: 'parent'|'child', node }

  useEffect(() => {
    let cancelled = false
    setStructure(null)
    setExtraction(null)
    setError(null)
    setSelected(null)
    api
      .documentStructure(documentId)
      .then((data) => !cancelled && setStructure(data))
      .catch((e) => !cancelled && setError(e))
    api
      .extraction(documentId)
      .then((data) => !cancelled && setExtraction(data))
      .catch((e) => !cancelled && setError(e))
    return () => {
      cancelled = true
    }
  }, [documentId])

  if (error) {
    return (
      <div className="error-box">
        <span className="stage-tag">{error.stage}</span>
        {error.message}
      </div>
    )
  }

  if (!structure) {
    return <div className="loading-text">Loading structure…</div>
  }

  const ocrCount = extraction ? extraction.filter((p) => p.ocr).length : 0

  return (
    <div>
      <div className="panel">
        <h2>Document Structure</h2>
        <p style={{ color: 'var(--text-dim)' }}>
          {structure.filename} — {structure.parents.length} parent chunks,{' '}
          {structure.parents.reduce((n, p) => n + p.children.length, 0)} child chunks.
          Click any node to inspect it.
        </p>
      </div>

      <div className="panel">
        <StructureGraph parents={structure.parents} selected={selected} onSelect={setSelected} />
      </div>

      <div className="panel">
        <div className="panel-head-row">
          <h3 style={{ margin: 0 }}>Extraction Preview</h3>
          {extraction && (
            <span className="badge" style={{ marginRight: 0 }}>
              {ocrCount} of {extraction.length} pages OCR'd
            </span>
          )}
        </div>
        <p style={{ color: 'var(--text-dim)', fontSize: 14 }}>
          Exactly what was pulled out of the document: the embedded text layer where available,
          Tesseract OCR for scanned / image-only pages.
        </p>
        {extraction && (
          <div className="extraction-list">
            {extraction.map((p) => (
              <div key={p.page_number} className="extraction-page">
                <div className="extraction-meta">
                  <span className="rank-badge">Page {p.page_number}</span>
                  {p.ocr && <span className="ocr-badge">OCR</span>}
                  <span className="extraction-chars">{p.char_count} chars</span>
                </div>
                <div className="extraction-text">
                  {p.text || <em className="loading-text">(no text extracted)</em>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="modal-head">
              <h3 style={{ margin: 0 }}>{selected.type === 'parent' ? 'Parent Chunk' : 'Child Chunk'}</h3>
              <button className="secondary" onClick={() => setSelected(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: 12 }}>
                <span className="badge">ID: {selected.node.id.slice(0, 8)}</span>
                {selected.type === 'child' && <span className="badge">Parent: {selected.parentId.slice(0, 8)}</span>}
                {selected.node.page_number ? <span className="badge">Page {selected.node.page_number}</span> : null}
              </div>
              <p style={{ margin: 0, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{selected.node.text}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StructureGraph({ parents, selected, onSelect }) {
  const gridRef = useRef(null)
  const [positions, setPositions] = useState({})

  const measure = useCallback(() => {
    const grid = gridRef.current
    if (!grid) return
    const rect = grid.getBoundingClientRect()
    const pos = {}
    grid.querySelectorAll('[data-node-id]').forEach((el) => {
      const r = el.getBoundingClientRect()
      pos[el.dataset.nodeId] = {
        x: r.left - rect.left,
        y: r.top - rect.top,
        w: r.width,
        h: r.height,
      }
    })
    setPositions(pos)
  }, [])

  useLayoutEffect(() => {
    measure()
  }, [parents, measure])

  useEffect(() => {
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [measure])

  const edges = []
  parents.forEach((p) => p.children.forEach((c) => edges.push({ from: p.id, to: c.id })))

  return (
    <div className="graph-scroll">
      <div
        className="graph-grid"
        ref={gridRef}
        style={{ gridTemplateColumns: `repeat(${parents.length}, 260px)` }}
      >
        <svg className="graph-edges" aria-hidden="true">
          {edges.map((e) => {
            const a = positions[e.from]
            const b = positions[e.to]
            if (!a || !b) return null
            const x1 = a.x + a.w / 2
            const y1 = a.y + a.h
            const x2 = b.x + b.w / 2
            const y2 = b.y
            const mid = (y1 + y2) / 2
            return (
              <path
                key={`${e.from}-${e.to}`}
                d={`M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`}
                className="graph-edge"
              />
            )
          })}
        </svg>
        {parents.map((parent) => (
          <div key={parent.id} className="graph-column">
            <div
              className={`graph-parent${selected?.type === 'parent' && selected.node.id === parent.id ? ' is-selected' : ''}`}
              data-node-id={parent.id}
              onClick={() => onSelect({ type: 'parent', node: parent })}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSelect({ type: 'parent', node: parent })}
            >
              <div className="graph-node-title">
                Parent {parent.order + 1}
                {parent.page_number ? ` · page ${parent.page_number}` : ''}
              </div>
              <div className="graph-node-count">{parent.children.length} children</div>
              <div className="graph-node-preview">{parent.text}</div>
            </div>
            {parent.children.map((child) => (
              <div
                key={child.id}
                className={`graph-child${selected?.type === 'child' && selected.node.id === child.id ? ' is-selected' : ''}`}
                data-node-id={child.id}
                onClick={() => onSelect({ type: 'child', node: child, parentId: parent.id })}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onSelect({ type: 'child', node: child, parentId: parent.id })}
              >
                <div className="graph-child-meta">
                  Child {child.order + 1}
                  {child.page_number ? ` · p${child.page_number}` : ''}
                </div>
                <div className="graph-node-preview">{child.text}</div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
