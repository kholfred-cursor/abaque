import { Fragment, type ReactNode } from "react";

/** A deliberately small Markdown subset for the facilitator's texts, rendered as React
 * elements (never as HTML): paragraphs, line breaks, "- " lists, **bold** and *italic*.
 * Links and images are not interpreted: a vote page never sends the voter elsewhere. */
function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(
      match[1] !== undefined ? (
        <strong key={match.index}>{match[1]}</strong>
      ) : (
        <em key={match.index}>{match[2]}</em>
      ),
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function withBreaks(lines: string[]): ReactNode[] {
  return lines.map((line, index) => (
    <Fragment key={index}>
      {index > 0 && <br />}
      {inline(line)}
    </Fragment>
  ));
}

export function Markdown({ text }: { text: string }) {
  const blocks = text
    .replace(/\r\n?/g, "\n")
    .split(/\n\s*\n/)
    .map((block) => block.split("\n").filter((line) => line.trim() !== ""))
    .filter((lines) => lines.length > 0);
  return (
    <>
      {blocks.map((lines, index) =>
        lines.every((line) => /^\s*[-*] /.test(line)) ? (
          <ul key={index}>
            {lines.map((line, n) => (
              <li key={n}>{inline(line.replace(/^\s*[-*] /, ""))}</li>
            ))}
          </ul>
        ) : (
          <p key={index}>{withBreaks(lines)}</p>
        ),
      )}
    </>
  );
}
