import { getApiBase, ApiError } from "@/lib/api/client";
import { normalizeSources } from "@/lib/api/normalize";
import type { ChatStatus, CitationInfo, QuerySource } from "@/lib/types";

export interface StreamHandlers {
  onStatus?: (status: ChatStatus, detail?: string) => void;
  onQueryRewrite?: (original: string, rewritten: string) => void;
  /** Called again with a fresh list if the agent retries retrieval, so replace rather than append. */
  onSources: (sources: QuerySource[], timingsMs?: Record<string, number>) => void;
  onToken: (token: string) => void;
  onGroundedness?: (grounded: boolean | null, unsupportedClaims: string[]) => void;
  onCitations?: (info: CitationInfo) => void;
  onDone: (info: { conversationId?: string }) => void;
  onError: (error: Error) => void;
}

export interface StreamQueryOptions extends StreamHandlers {
  query: string;
  /** Continue an existing conversation so follow-up questions have memory. */
  conversationId?: string | null;
  collectionId?: string | null;
  signal?: AbortSignal;
}

type Json = Record<string, unknown>;

function toCitationInfo(p: Json): CitationInfo {
  const claims = Array.isArray(p.claims) ? (p.claims as Json[]) : [];
  const invalid = Array.isArray(p.invalid_inline) ? (p.invalid_inline as Json[]) : [];
  return {
    claims: claims.map((c) => ({
      text: String(c.text ?? ""),
      sourceIds: Array.isArray(c.source_ids) ? (c.source_ids as number[]) : [],
    })),
    confidence: (p.confidence as CitationInfo["confidence"]) ?? undefined,
    droppedSourceIds: Number(p.dropped_source_ids ?? 0),
    invalidInline: invalid.map((i) => ({ filename: String(i.filename ?? ""), page: Number(i.page ?? 0) })),
  };
}

/** Dispatches one SSE event. Returns false once the stream is finished. */
function handleEvent(data: string, h: StreamHandlers, finish: (id?: string) => void): boolean {
  if (!data || data === "[DONE]") {
    finish();
    return false;
  }

  let p: Json;
  try {
    p = JSON.parse(data) as Json;
  } catch {
    h.onToken(data);
    return true;
  }

  switch (String(p.type ?? "")) {
    case "route":
      if (p.route === "needs_retrieval") h.onStatus?.("searching", "Searching your documents…");
      else h.onStatus?.("generating", "Answering directly, no document search needed");
      break;
    case "query_rewrite":
      h.onQueryRewrite?.(String(p.original ?? ""), String(p.rewritten ?? ""));
      h.onStatus?.("searching", `Searching for: ${String(p.rewritten ?? "")}`);
      break;
    case "sources": {
      const sources = normalizeSources(p.sources);
      h.onSources(sources, (p.timings_ms as Record<string, number> | undefined) ?? undefined);
      const n = sources.length;
      h.onStatus?.("generating", n ? `Found ${n} passage${n === 1 ? "" : "s"}` : "No matching passages found");
      break;
    }
    case "chunk_grades":
      if (p.weak) h.onStatus?.("searching", "Results looked weak, trying a different search");
      else h.onStatus?.("generating", "Writing the answer…");
      break;
    case "chunk": {
      const token = String(p.content ?? "");
      if (token) h.onToken(token);
      break;
    }
    case "groundedness":
      h.onGroundedness?.(
        p.grounded === null || p.grounded === undefined ? null : Boolean(p.grounded),
        Array.isArray(p.unsupported_claims) ? p.unsupported_claims.map(String) : []
      );
      break;
    case "citations":
      h.onCitations?.(toCitationInfo(p));
      break;
    case "done":
      finish(typeof p.conversation_id === "string" ? p.conversation_id : undefined);
      return false;
    case "error":
      h.onError(new Error(String(p.message ?? "Stream error")));
      return false;
    default: {
      // Older backends stream bare token fields.
      const token = String(p.content ?? p.token ?? p.text ?? p.delta ?? "");
      if (token) h.onToken(token);
    }
  }
  return true;
}

export async function streamQuery(options: StreamQueryOptions): Promise<void> {
  let finished = false;
  let conversationId: string | undefined;
  const finish = (id?: string) => {
    if (id) conversationId = id;
    if (finished) return;
    finished = true;
    options.onDone({ conversationId });
  };
  // An error event ends the stream; onDone must not follow it.
  const handlers: StreamHandlers = {
    ...options,
    onError: (e) => {
      finished = true;
      options.onError(e);
    },
  };

  const res = await fetch(`${getApiBase()}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      query: options.query,
      conversation_id: options.conversationId ?? undefined,
      collection_id: options.collectionId ?? undefined,
    }),
    signal: options.signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText);
  }

  if (!(res.headers.get("content-type") ?? "").includes("text/event-stream")) {
    const json = (await res.json()) as Json;
    if (json.sources) options.onSources(normalizeSources(json.sources));
    const answer = String(json.answer ?? json.response ?? json.content ?? "");
    if (answer) options.onToken(answer);
    finish();
    return;
  }

  if (!res.body) throw new ApiError(500, "No response stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let open = true;

  const dispatch = (block: string) => {
    for (const line of block.split("\n")) {
      if (open && line.startsWith("data:")) open = handleEvent(line.slice(5).trim(), handlers, finish);
    }
  };

  while (open) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) dispatch(part);
  }

  if (open && buffer.trim()) dispatch(buffer);
  if (!open) reader.cancel().catch(() => {});
  finish();
}
