"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertCircle,
  Check,
  Copy,
  FileSearch,
  Loader2,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { bestSupportingLine, linkCitations, splitSentences } from "@/lib/citations";
import type { ChatMessage as Message, QuerySource } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

// Markdown + highlight.js are only needed once an answer arrives, so keep them out of the page's first load.
const Markdown = dynamic(() => import("@/components/chat/markdown").then((m) => m.Markdown), {
  ssr: false,
  loading: () => null,
});

function sourceLabel(s: QuerySource) {
  return `${s.documentName ?? "Unknown document"}${s.page ? `, page ${s.page}` : ""}`;
}

function passageLines(text: string) {
  return text.split(/\n+/).map((l) => l.trim()).filter(Boolean);
}

/** One passage line; markdown headings ("## Limits") render as small section labels, not raw syntax. */
function PassageLine({ line }: { line: string }) {
  const heading = line.match(/^#{1,6}\s+(.*)$/);
  if (heading) return <p className="pt-1 font-medium text-foreground/80">{heading[1]}</p>;
  return <p>{line}</p>;
}

/** The sentence of a source that best supports what the answer says about it (for the margin note). */
function evidenceFor(source: QuerySource, claims: string[], answer: string): string | null {
  if (!source.chunkText) return null;
  const sentences = passageLines(source.chunkText)
    .filter((l) => !l.startsWith("#"))
    .flatMap(splitSentences);
  const best = bestSupportingLine(sentences, claims.length ? claims : [answer]);
  return best >= 0 ? sentences[best] : sentences[0] ?? null;
}

/** The cited chunk, with the sentence that best supports the claims marked in place and scrolled into view. */
function Passage({ text, claims }: { text: string; claims: string[] }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const markRef = useRef<HTMLElement>(null);
  const paragraphs = passageLines(text).map((line) =>
    /^#{1,6}\s/.test(line) ? { heading: line, sentences: [] as string[] } : { heading: null, sentences: splitSentences(line) }
  );
  const flat = paragraphs.flatMap((p) => p.sentences);
  const best = bestSupportingLine(flat, claims);

  useEffect(() => {
    const box = boxRef.current;
    const mark = markRef.current;
    if (box && mark) box.scrollTop = mark.offsetTop - box.offsetTop - box.clientHeight / 3;
  }, []);

  let index = -1;
  return (
    <div ref={boxRef} className="relative mt-2 max-h-48 space-y-1.5 overflow-y-auto text-xs leading-relaxed text-muted-foreground">
      {paragraphs.map((p, i) =>
        p.heading ? (
          <PassageLine key={i} line={p.heading} />
        ) : (
          <p key={i}>
            {p.sentences.map((sentence, j) => {
              index += 1;
              return index === best ? (
                <mark key={j} ref={markRef} className="rounded-sm bg-highlight px-0.5 text-highlight-foreground">
                  {sentence}{" "}
                </mark>
              ) : (
                <span key={j}>{sentence} </span>
              );
            })}
          </p>
        )
      )}
    </div>
  );
}

/** Citation number set like a highlighter mark; the popover shows the passage it points at. */
function CitationChip({
  n,
  source,
  claims,
  onActive,
  onShowInPanel,
}: {
  n: number;
  source: QuerySource;
  claims: string[];
  onActive: (n: number | null) => void;
  onShowInPanel: () => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Source ${n}: ${sourceLabel(source)}`}
          onMouseEnter={() => onActive(n)}
          onMouseLeave={() => onActive(null)}
          onFocus={() => onActive(n)}
          onBlur={() => onActive(null)}
          className="mx-0.5 inline-flex h-[1.15em] min-w-[1.15em] -translate-y-[0.35em] items-center justify-center rounded-sm bg-highlight px-1 align-baseline font-sans text-[0.7em] font-semibold tabular-nums leading-none text-highlight-foreground transition-shadow hover:shadow-[0_0_0_2px_var(--highlight)]"
        >
          {n}
        </button>
      </PopoverTrigger>
      <PopoverContent>
        <p className="break-words text-sm font-medium">{sourceLabel(source)}</p>
        {(source.heading || source.section || source.score !== undefined) && (
          <p className="text-xs text-muted-foreground">
            {source.heading || source.section}
            {(source.heading || source.section) && source.score !== undefined && ", "}
            {source.score !== undefined && `relevance ${source.score.toFixed(2)}`}
            {source.rerankScore !== undefined && `, rerank ${source.rerankScore.toFixed(2)}`}
          </p>
        )}
        {source.chunkText && <Passage text={source.chunkText} claims={claims} />}
        {claims.length > 0 && (
          <div className="mt-2 border-t pt-2">
            <p className="text-xs font-medium">Supports</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
              {claims.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}
        <button type="button" onClick={onShowInPanel} className="mt-2 text-xs font-medium text-primary hover:underline">
          Show the full passage
        </button>
      </PopoverContent>
    </Popover>
  );
}

/** Wide screens: the evidence for each source sits in the margin beside the answer, like an annotated page. */
function Margin({
  sources,
  claimsFor,
  answer,
  active,
}: {
  sources: QuerySource[];
  claimsFor: (n: number) => string[];
  answer: string;
  active: number | null;
}) {
  return (
    <aside aria-label="Sources for this answer" className="hidden xl:block">
      <ol className="space-y-4 border-l border-border pl-5">
        {sources.map((s, i) => {
          const n = i + 1;
          const evidence = evidenceFor(s, claimsFor(n), answer);
          return (
            <li
              key={s.chunkId ?? i}
              className={cn(
                "rounded-md p-2 -m-2 transition-colors",
                active === n && "bg-highlight/40 dark:bg-highlight"
              )}
            >
              <p className="flex items-baseline gap-2 text-sm">
                <span className="inline-flex min-w-5 justify-center rounded-sm bg-highlight px-1 text-xs font-semibold tabular-nums text-highlight-foreground">
                  {n}
                </span>
                <span className="min-w-0 truncate font-medium">{s.documentName ?? "Unknown document"}</span>
                {s.page ? <span className="shrink-0 text-xs text-muted-foreground">p. {s.page}</span> : null}
              </p>
              {evidence && (
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
                  <mark className="box-decoration-clone rounded-sm bg-highlight/70 px-0.5 text-highlight-foreground dark:bg-highlight">
                    {evidence}
                  </mark>
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </aside>
  );
}

/** Ranked retrieved passages in full; the "show raw context" view on every screen size. */
function SourcesPanel({
  id,
  sources,
  open,
  onToggle,
}: {
  id: string;
  sources: QuerySource[];
  open: boolean;
  onToggle: (open: boolean) => void;
}) {
  const top = Math.max(...sources.map((s) => s.score ?? 0), 0.0001);
  return (
    <details open={open} onToggle={(e) => onToggle(e.currentTarget.open)} className="group max-w-[68ch] rounded-lg border bg-card">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3 text-sm text-muted-foreground hover:text-foreground sm:min-h-9">
        <FileSearch className="size-4" aria-hidden />
        {sources.length} source passage{sources.length === 1 ? "" : "s"}
        <span className="ml-auto text-xs group-open:hidden">Show</span>
        <span className="ml-auto hidden text-xs group-open:inline">Hide</span>
      </summary>
      <ol aria-label="Retrieved passages" className="space-y-3 border-t px-3 py-3">
        {sources.map((s, i) => (
          <li key={s.chunkId ?? i} id={`${id}-src-${i + 1}`} className="scroll-mt-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="inline-flex min-w-5 justify-center rounded-sm bg-highlight px-1 text-xs font-semibold tabular-nums text-highlight-foreground">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 truncate font-medium">{sourceLabel(s)}</span>
              {s.score !== undefined && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground" title="Relevance to the question">
                  <span className="h-1 w-12 overflow-hidden rounded-full bg-muted" aria-hidden>
                    <span className="block h-full rounded-full bg-primary" style={{ width: `${(s.score / top) * 100}%` }} />
                  </span>
                  {s.score.toFixed(2)}
                </span>
              )}
            </div>
            {s.chunkText && (
              <div className="mt-1.5 space-y-1 pl-7 text-[13px] leading-relaxed text-muted-foreground">
                {passageLines(s.chunkText).map((line, j) => (
                  <PassageLine key={j} line={line} />
                ))}
              </div>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}

interface ChatMessageProps {
  message: Message;
  onRegenerate?: () => void;
  onFeedback?: (value: "up" | "down", comment?: string) => void;
}

// 44px touch targets on phones, compact on desktop.
const actionClass = "size-11 sm:size-8";

export function ChatMessage({ message, onRegenerate, onFeedback }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [askingWhy, setAskingWhy] = useState(false);
  const [why, setWhy] = useState("");
  const [active, setActive] = useState<number | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[70%] whitespace-pre-wrap break-words rounded-lg bg-secondary px-4 py-2.5 text-[15px] leading-relaxed text-secondary-foreground">
          {message.content}
        </p>
      </div>
    );
  }

  const done = !message.isStreaming;
  const sources = message.sources ?? [];
  const claimsFor = (n: number) =>
    message.citations?.claims.filter((c) => c.sourceIds.includes(n)).map((c) => c.text) ?? [];

  const showInPanel = (n?: number) => {
    setPanelOpen(true);
    requestAnimationFrame(() => {
      const target = n
        ? rootRef.current?.querySelector(`#${CSS.escape(`${message.id}-src-${n}`)}`)
        : rootRef.current?.querySelector("details");
      target?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  };

  const copy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const confidence = message.citations?.confidence;

  return (
    <div ref={rootRef} className="grid gap-x-10 gap-y-4 xl:grid-cols-[minmax(0,68ch)_minmax(0,1fr)]">
      <div className="min-w-0 space-y-4">
        {message.isStreaming && !message.content && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {message.statusDetail ?? "Thinking…"}
          </p>
        )}

        {message.content && (
          <div className="answer prose break-words">
            <Markdown
              renderCitation={(n) =>
                sources[n - 1] ? (
                  <CitationChip
                    n={n}
                    source={sources[n - 1]}
                    claims={claimsFor(n)}
                    onActive={setActive}
                    onShowInPanel={() => showInPanel(n)}
                  />
                ) : null
              }
            >
              {linkCitations(message.content, sources)}
            </Markdown>
            {message.isStreaming && <span className="ml-0.5 inline-block animate-pulse" aria-hidden>▍</span>}
          </div>
        )}

        {message.error && (
          <p className="flex items-center gap-2 text-sm text-destructive" role="alert">
            <AlertCircle className="size-4 shrink-0" aria-hidden />
            {message.error}
          </p>
        )}

        {done && (message.grounded !== undefined || confidence || message.rewrite) && (
          <div className="space-y-1 text-sm">
            {message.grounded === true && (
              <p className="flex items-center gap-2 text-success">
                <ShieldCheck className="size-4 shrink-0" aria-hidden />
                <span>
                  Checked against its sources{confidence ? `, ${confidence} confidence` : ""}.
                </span>
              </p>
            )}
            {message.grounded === false && (
              <p className="flex items-center gap-2 text-warning">
                <ShieldAlert className="size-4 shrink-0" aria-hidden />
                <span>Parts of this answer are not supported by the sources. Check them before relying on it.</span>
              </p>
            )}
            {message.grounded === undefined && confidence && (
              <p className="text-muted-foreground">Confidence: {confidence}.</p>
            )}
            {message.rewrite && message.rewrite.rewritten !== message.rewrite.original && (
              <p className="text-muted-foreground">Searched for “{message.rewrite.rewritten}”</p>
            )}
          </div>
        )}

        {sources.length > 0 && (
          <SourcesPanel id={message.id} sources={sources} open={panelOpen} onToggle={setPanelOpen} />
        )}

        {done && (
          <div className="-ml-2 flex items-center gap-0.5 text-muted-foreground">
            {message.content && (
              <Button variant="ghost" size="icon" className={actionClass} aria-label={copied ? "Copied" : "Copy answer"} onClick={copy}>
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              </Button>
            )}
            {onRegenerate && (
              <Button variant="ghost" size="icon" className={actionClass} aria-label="Regenerate answer" onClick={onRegenerate}>
                <RotateCcw className="size-3.5" />
              </Button>
            )}
            {sources.length > 0 && (
              <Button variant="ghost" size="icon" className={actionClass} aria-label="Show raw context" onClick={() => showInPanel()}>
                <FileSearch className="size-3.5" />
              </Button>
            )}
            {onFeedback && message.content && !message.error && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(actionClass, message.feedback === "up" && "text-primary")}
                  aria-label="Good answer"
                  aria-pressed={message.feedback === "up"}
                  disabled={!!message.feedback}
                  onClick={() => onFeedback("up")}
                >
                  <ThumbsUp className="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(actionClass, message.feedback === "down" && "text-destructive")}
                  aria-label="Bad answer"
                  aria-pressed={message.feedback === "down" || askingWhy}
                  disabled={!!message.feedback}
                  onClick={() => setAskingWhy(true)}
                >
                  <ThumbsDown className="size-3.5" />
                </Button>
              </>
            )}
          </div>
        )}

        {askingWhy && !message.feedback && onFeedback && (
          <form
            className="flex max-w-[68ch] flex-col gap-2 rounded-lg border bg-card p-3 sm:flex-row sm:items-center"
            onSubmit={(e) => {
              e.preventDefault();
              onFeedback("down", why.trim());
              setAskingWhy(false);
            }}
          >
            <label htmlFor={`${message.id}-why`} className="sr-only">What went wrong? (optional)</label>
            <input
              id={`${message.id}-why`}
              autoFocus
              value={why}
              onChange={(e) => setWhy(e.target.value)}
              maxLength={2000}
              placeholder="What went wrong? (optional)"
              className="min-h-11 flex-1 rounded-md border bg-background px-3 text-sm sm:min-h-9"
            />
            <div className="flex gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setAskingWhy(false)}>Cancel</Button>
              <Button type="submit" size="sm">Send feedback</Button>
            </div>
          </form>
        )}
      </div>

      {sources.length > 0 && message.content && (
        <Margin sources={sources} claimsFor={claimsFor} answer={message.content} active={active} />
      )}
    </div>
  );
}
