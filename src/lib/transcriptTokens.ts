export interface TranscriptTextPart {
  kind: "text";
  text: string;
}

export interface TranscriptWordPart {
  kind: "word";
  text: string;
  tokenIndex: number;
}

export type TranscriptRenderPart = TranscriptTextPart | TranscriptWordPart;

const officialTokenPattern =
  /[£$€]?\d+(?:[,.]\d+)*(?:-[A-Za-z0-9]+)?|[A-Za-z0-9]+(?:[’'][A-Za-z0-9]+)?(?:-[A-Za-z0-9]+)*/g;

export function tokenizeTranscriptText(text: string): TranscriptRenderPart[] {
  const parts: TranscriptRenderPart[] = [];
  let nextTextStart = 0;
  let tokenIndex = 0;

  for (const match of text.matchAll(officialTokenPattern)) {
    const token = match[0];
    const matchIndex = match.index ?? 0;

    if (matchIndex > nextTextStart) {
      parts.push({ kind: "text", text: text.slice(nextTextStart, matchIndex) });
    }

    parts.push({ kind: "word", text: token, tokenIndex });
    tokenIndex += 1;
    nextTextStart = matchIndex + token.length;
  }

  if (nextTextStart < text.length) {
    parts.push({ kind: "text", text: text.slice(nextTextStart) });
  }

  return parts;
}
