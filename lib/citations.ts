import type { QuerySource } from "@/lib/types";

// "(pricing.xlsx, p. 1)" / "(report.pdf, page 7)" as the backend prompt asks the model to cite.
const INLINE = /\(([^()\n]+?),\s*(?:p\.|page)\s*(\d+)\)/gi;

/**
 * Turn inline "(file, p. N)" citations into markdown links "[n](#cite-n)", where n is the 1-based
 * position of the matching retrieved source. Citations that match no retrieved source stay as plain
 * text: an invented reference must never look verified.
 */
export function linkCitations(text: string, sources: QuerySource[]): string {
  return text.replace(INLINE, (whole, file: string, page: string) => {
    const name = file.trim().toLowerCase();
    const i = sources.findIndex(
      (s) =>
        (s.documentName ?? "").toLowerCase() === name &&
        (s.page === undefined || s.page === null || String(s.page) === page)
    );
    return i < 0 ? whole : `[${i + 1}](#cite-${i + 1})`;
  });
}

const words = (t: string) => new Set(t.toLowerCase().match(/[a-z0-9]+(?:[-.][a-z0-9]+)*/g) ?? []);

/**
 * Index of the passage line that best supports the claims (most shared words, identifiers included), or -1
 * when nothing overlaps. Used to highlight and scroll to the evidence inside a long chunk.
 */
export function bestSupportingLine(lines: string[], claims: string[]): number {
  const target = words(claims.join(" "));
  let best = -1;
  let bestScore = 0;
  lines.forEach((line, i) => {
    let score = 0;
    for (const w of words(line)) if (target.has(w) && w.length > 2) score += 1;
    if (score > bestScore) [best, bestScore] = [i, score];
  });
  return best;
}

