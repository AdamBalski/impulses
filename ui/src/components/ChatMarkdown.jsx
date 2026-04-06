function parseSegments(text) {
  const source = typeof text === 'string' ? text : '';
  const segments = [];
  const regex = /```([\w.+-]*)\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(source)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        type: 'text',
        content: source.slice(lastIndex, match.index),
      });
    }
    segments.push({
      type: 'code',
      language: match[1] || '',
      content: match[2] || '',
    });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < source.length) {
    segments.push({
      type: 'text',
      content: source.slice(lastIndex),
    });
  }

  if (segments.length === 0) {
    segments.push({ type: 'text', content: source });
  }

  return segments;
}

function renderInline(text, keyPrefix) {
  const source = typeof text === 'string' ? text : '';
  const parts = [];
  const regex = /(`[^`]+`)|(\*\*[\s\S]+?\*\*)|(~~[\s\S]+?~~)|(\*(?!\s)(?:[^*]|\\\*)+?\*)|(_(?!\s)(?:[^_]|\\_)+?_)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(source)) !== null) {
    if (match.index > lastIndex) {
      parts.push(source.slice(lastIndex, match.index));
    }

    if (match[1]) {
      parts.push(
        <code
          key={`${keyPrefix}-code-${match.index}`}
          className="chat-markdown-inline-code"
        >
          {match[1].slice(1, -1)}
        </code>,
      );
    } else if (match[2]) {
      const content = match[2].slice(2, -2);
      parts.push(
        <strong key={`${keyPrefix}-strong-${match.index}`}>
          {renderInline(content, `${keyPrefix}-strong-${match.index}`)}
        </strong>,
      );
    } else if (match[3]) {
      const content = match[3].slice(2, -2);
      parts.push(
        <del key={`${keyPrefix}-del-${match.index}`}>
          {renderInline(content, `${keyPrefix}-del-${match.index}`)}
        </del>,
      );
    } else if (match[4] || match[5]) {
      const markerWrapped = match[4] || match[5];
      const content = markerWrapped.slice(1, -1);
      parts.push(
        <em key={`${keyPrefix}-em-${match.index}`}>
          {renderInline(content, `${keyPrefix}-em-${match.index}`)}
        </em>,
      );
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < source.length) {
    parts.push(source.slice(lastIndex));
  }

  return parts.length > 0 ? parts : source;
}

function splitTableRow(line) {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((cell) => cell.trim());
}

function isTableSeparator(line) {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function parseTextBlocks(text) {
  const source = typeof text === 'string' ? text.replace(/\r\n/g, '\n') : '';
  const lines = source.split('\n');
  const blocks = [];
  let paragraphLines = [];
  let list = null;
  let quoteLines = [];

  function flushParagraph() {
    const content = paragraphLines.join(' ').trim();
    if (content) {
      blocks.push({ type: 'paragraph', content });
    }
    paragraphLines = [];
  }

  function flushList() {
    if (list && list.items.length > 0) {
      blocks.push(list);
    }
    list = null;
  }

  function flushQuote() {
    const content = quoteLines.join('\n').trim();
    if (content) {
      blocks.push({ type: 'blockquote', content });
    }
    quoteLines = [];
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }

    if (
      trimmed.includes('|') &&
      index + 1 < lines.length &&
      lines[index + 1].trim().includes('|') &&
      isTableSeparator(lines[index + 1])
    ) {
      flushParagraph();
      flushList();
      flushQuote();
      const headers = splitTableRow(trimmed);
      const rows = [];
      index += 2;
      while (index < lines.length) {
        const rowLine = lines[index].trim();
        if (!rowLine || !rowLine.includes('|')) {
          index -= 1;
          break;
        }
        rows.push(splitTableRow(rowLine));
        index += 1;
      }
      blocks.push({
        type: 'table',
        headers,
        rows,
      });
      continue;
    }

    if (/^([-*_])\1{2,}$/.test(trimmed)) {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({ type: 'hr' });
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({
        type: 'heading',
        level: headingMatch[1].length,
        content: headingMatch[2].trim(),
      });
      continue;
    }

    const quoteMatch = trimmed.match(/^>\s?(.*)$/);
    if (quoteMatch) {
      flushParagraph();
      flushList();
      quoteLines.push(quoteMatch[1]);
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (unorderedMatch) {
      flushParagraph();
      flushQuote();
      if (!list || list.type !== 'unordered-list') {
        flushList();
        list = { type: 'unordered-list', items: [] };
      }
      list.items.push(unorderedMatch[1].trim());
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      flushParagraph();
      flushQuote();
      if (!list || list.type !== 'ordered-list') {
        flushList();
        list = { type: 'ordered-list', items: [] };
      }
      list.items.push(orderedMatch[1].trim());
      continue;
    }

    flushList();
    flushQuote();
    paragraphLines.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushQuote();

  return blocks;
}

export default function ChatMarkdown({ content }) {
  const segments = parseSegments(content);

  return (
    <div className="chat-markdown">
      {segments.map((segment, index) => {
        if (segment.type === 'code') {
          return (
            <div key={index} className="chat-markdown-code-block">
              {segment.language && (
                <div className="chat-code-language">{segment.language}</div>
              )}
              <pre>
                <code>{segment.content}</code>
              </pre>
            </div>
          );
        }

        if (!segment.content.trim()) {
          return null;
        }

        const blocks = parseTextBlocks(segment.content);

        return blocks.map((block, blockIndex) => {
          const key = `${index}-${blockIndex}`;

          if (block.type === 'heading') {
            const Tag = `h${block.level}`;
            return (
              <Tag key={key} className={`chat-markdown-heading chat-markdown-heading--h${block.level}`}>
                {renderInline(block.content, key)}
              </Tag>
            );
          }

          if (block.type === 'unordered-list' || block.type === 'ordered-list') {
            const ListTag = block.type === 'unordered-list' ? 'ul' : 'ol';
            return (
              <ListTag key={key} className="chat-markdown-list">
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>
                ))}
              </ListTag>
            );
          }

          if (block.type === 'blockquote') {
            return (
              <blockquote key={key} className="chat-markdown-blockquote">
                <ChatMarkdown content={block.content} />
              </blockquote>
            );
          }

          if (block.type === 'hr') {
            return <hr key={key} className="chat-markdown-rule" />;
          }

          if (block.type === 'table') {
            return (
              <div key={key} className="chat-markdown-table-wrap">
                <table className="chat-markdown-table">
                  <thead>
                    <tr>
                      {block.headers.map((header, headerIndex) => (
                        <th key={`${key}-header-${headerIndex}`}>
                          {renderInline(header, `${key}-header-${headerIndex}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row, rowIndex) => (
                      <tr key={`${key}-row-${rowIndex}`}>
                        {block.headers.map((_, cellIndex) => (
                          <td key={`${key}-cell-${rowIndex}-${cellIndex}`}>
                            {renderInline(row[cellIndex] || '', `${key}-cell-${rowIndex}-${cellIndex}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }

          return (
            <p key={key} className="chat-markdown-paragraph">
              {renderInline(block.content, key)}
            </p>
          );
        });
      })}
    </div>
  );
}
