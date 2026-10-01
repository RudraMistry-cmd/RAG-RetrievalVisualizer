// Minimal, dependency-free Markdown parser for LLM answers.
// Produces a plain data tree (no HTML strings), rendered by Markdown.jsx.

export function cleanLlmText(text) {
  return String(text ?? '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .replace(/<think>[\s\S]*$/i, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/?[a-zA-Z][^>\n]*>/g, '')
    .replace(/\r\n/g, '\n')
    .trim()
}

const INLINE = /(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\*[^*\s][^*\n]*\*|(?<![A-Za-z0-9])_[^_\s][^_\n]*_(?![A-Za-z0-9]))/

export function parseInline(text) {
  const out = []
  let rest = text
  while (rest) {
    const m = INLINE.exec(rest)
    if (!m) {
      out.push({ t: 'text', v: rest })
      break
    }
    if (m.index > 0) out.push({ t: 'text', v: rest.slice(0, m.index) })
    const tok = m[0]
    if (tok.startsWith('**') || tok.startsWith('__')) out.push({ t: 'strong', c: parseInline(tok.slice(2, -2)) })
    else if (tok.startsWith('`')) out.push({ t: 'code', v: tok.slice(1, -1) })
    else out.push({ t: 'em', c: parseInline(tok.slice(1, -1)) })
    rest = rest.slice(m.index + tok.length)
  }
  return out
}

const BULLET = /^\s*[-*+•]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/
const HEADING = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/
const FENCE = /^\s*```/

export function parseBlocks(raw) {
  const lines = cleanLlmText(raw).split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    if (FENCE.test(line)) {
      const code = []
      i++
      while (i < lines.length && !FENCE.test(lines[i])) code.push(lines[i++])
      i++
      blocks.push({ t: 'pre', v: code.join('\n') })
      continue
    }
    const h = HEADING.exec(line)
    if (h) {
      blocks.push({ t: 'heading', level: Math.min(h[1].length, 3), c: parseInline(h[2]) })
      i++
      continue
    }
    if (BULLET.test(line) || NUMBERED.test(line)) {
      const ordered = NUMBERED.test(line) && !BULLET.test(line)
      const re = ordered ? NUMBERED : BULLET
      const items = []
      while (i < lines.length && re.test(lines[i])) {
        items.push(parseInline(re.exec(lines[i])[1]))
        i++
      }
      blocks.push({ t: ordered ? 'ol' : 'ul', items })
      continue
    }
    const para = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !FENCE.test(lines[i]) &&
      !HEADING.test(lines[i]) &&
      !BULLET.test(lines[i]) &&
      !NUMBERED.test(lines[i])
    ) {
      para.push(lines[i++].trim())
    }
    blocks.push({ t: 'p', lines: para.map(parseInline) })
  }
  return blocks
}
