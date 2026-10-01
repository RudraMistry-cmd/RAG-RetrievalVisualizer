import React from 'react'
import { parseBlocks } from './markdown.js'

function Inline({ nodes }) {
  return nodes.map((n, i) => {
    if (n.t === 'text') return <React.Fragment key={i}>{n.v}</React.Fragment>
    if (n.t === 'code') return <code key={i}>{n.v}</code>
    if (n.t === 'strong') return <strong key={i}><Inline nodes={n.c} /></strong>
    return <em key={i}><Inline nodes={n.c} /></em>
  })
}

export default function Markdown({ text }) {
  const blocks = parseBlocks(text)
  return (
    <div className="md">
      {blocks.map((b, i) => {
        if (b.t === 'heading') {
          const Tag = `h${b.level + 3}`
          return <Tag key={i}><Inline nodes={b.c} /></Tag>
        }
        if (b.t === 'ul' || b.t === 'ol') {
          const Tag = b.t
          return (
            <Tag key={i}>
              {b.items.map((it, j) => (
                <li key={j}><Inline nodes={it} /></li>
              ))}
            </Tag>
          )
        }
        if (b.t === 'pre') return <pre key={i}><code>{b.v}</code></pre>
        return (
          <p key={i}>
            {b.lines.map((ln, j) => (
              <React.Fragment key={j}>
                {j > 0 && <br />}
                <Inline nodes={ln} />
              </React.Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
