import { Fragment, type ReactNode } from 'react'

const BULLET = /^\s*[-*]\s+/
const NUMBER = /^\s*\d+[.)]\s+/
const HEADING = /^#{1,6}\s+/
const INLINE = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\s][^*\n]*\*)/g
const LINK = /(https:\/\/[^\s<>()]*[^\s<>().,;:!?'"])/g

/**
 * Just enough markdown for chat replies: paragraphs (single newlines kept), bullet and numbered lists,
 * headings (as bold lines), fenced code, **bold**, *italic*, `code` and https links. Builds React nodes, never HTML.
 */
export function Markdown({ text }: { text: string }) {
  return <div className="md">{blocks(text)}</div>
}

function isBlockStart(line: string) {
  return line.startsWith('```') || BULLET.test(line) || NUMBER.test(line) || HEADING.test(line)
}

function blocks(text: string): ReactNode[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const out: ReactNode[] = []
  let i = 0
  const take = (re: RegExp) => {
    const items: string[] = []
    while (i < lines.length && re.test(lines[i])) items.push(lines[i++].replace(re, ''))
    return items.map((t, k) => <li key={k}>{inline(t)}</li>)
  }
  while (i < lines.length) {
    const line = lines[i]
    const key = out.length
    if (line.startsWith('```')) {
      const body: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) body.push(lines[i++])
      i++ // the closing fence
      out.push(<pre key={key}><code>{body.join('\n')}</code></pre>)
    } else if (BULLET.test(line)) {
      out.push(<ul key={key}>{take(BULLET)}</ul>)
    } else if (NUMBER.test(line)) {
      out.push(<ol key={key}>{take(NUMBER)}</ol>)
    } else if (HEADING.test(line)) {
      out.push(<p key={key} className="md-h">{inline(line.replace(HEADING, ''))}</p>)
      i++
    } else if (!line.trim()) {
      i++
    } else {
      const para: string[] = []
      while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) para.push(lines[i++])
      out.push(
        <p key={key}>
          {para.map((l, k) => <Fragment key={k}>{k > 0 && <br />}{inline(l)}</Fragment>)}
        </p>,
      )
    }
  }
  return out
}

function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, k) => {
    if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) return <code key={k}>{part.slice(1, -1)}</code>
    if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) return <strong key={k}>{part.slice(2, -2)}</strong>
    if (part.length > 2 && part.startsWith('*') && part.endsWith('*')) return <em key={k}>{part.slice(1, -1)}</em>
    return <Fragment key={k}>{linkify(part)}</Fragment>
  })
}

/** Plain text with https links made clickable (they open in a new tab). */
export function linkify(text: string): ReactNode[] {
  return text.split(LINK).map((part, k) =>
    k % 2 ? <a key={k} href={part} target="_blank" rel="noreferrer">{part}</a> : part,
  )
}
