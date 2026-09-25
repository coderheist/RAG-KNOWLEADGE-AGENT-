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
