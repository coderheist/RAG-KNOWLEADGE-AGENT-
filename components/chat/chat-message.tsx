"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertCircle,
  Bot,
  Check,
  Copy,
  FileSearch,
  Loader2,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  User,
} from "lucide-react";
import { linkCitations } from "@/lib/citations";
import type { ChatMessage as Message, QuerySource } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
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

/** Superscript chip for an inline citation; the popover shows the passage it points at. */
function CitationChip({
  n,
  source,
  claims,
  onShowInPanel,
}: {
  n: number;
  source: QuerySource;
  claims: string[];
  onShowInPanel: () => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Source ${n}: ${sourceLabel(source)}`}
          className="mx-0.5 inline-flex h-4 min-w-4 -translate-y-1 items-center justify-center rounded bg-primary/15 px-1 align-baseline font-mono text-[10px] font-semibold leading-none text-primary hover:bg-primary/25"
        >
          {n}
        </button>
      </PopoverTrigger>
      <PopoverContent>
        <p className="break-words font-medium">{sourceLabel(source)}</p>
        <p className="text-xs text-muted-foreground">
          {[source.heading || source.section, source.score !== undefined && `relevance ${source.score.toFixed(2)}`,
            source.rerankScore !== undefined && `rerank ${source.rerankScore.toFixed(2)}`]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {source.chunkText && (
          <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-line text-xs text-muted-foreground">
            {source.chunkText}
          </p>
        )}
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
          Show in sources
        </button>
      </PopoverContent>
    </Popover>
  );
}

/** Ranked retrieved passages; doubles as the "show raw context" view. */
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
    <details
      open={open}
      onToggle={(e) => onToggle(e.currentTarget.open)}
      className="group rounded-lg border bg-background/60"
    >
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3 text-xs font-medium text-muted-foreground sm:min-h-9">
        <FileSearch className="size-3.5" aria-hidden />
        Sources · {sources.length} passage{sources.length === 1 ? "" : "s"}
        <span className="ml-auto group-open:hidden">Show</span>
        <span className="ml-auto hidden group-open:inline">Hide</span>
      </summary>
      <ol aria-label="Retrieved passages" className="space-y-2 border-t px-3 py-2">
        {sources.map((s, i) => (
          <li key={s.chunkId ?? i} id={`${id}-src-${i + 1}`} className="scroll-mt-4 rounded-md p-1 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-mono font-semibold text-primary">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate font-medium">{sourceLabel(s)}</span>
              {s.score !== undefined && (
                <span className="flex items-center gap-1.5 text-muted-foreground" title="Relevance">
                  <span className="h-1.5 w-12 overflow-hidden rounded-full bg-muted" aria-hidden>
                    <span className="block h-full rounded-full bg-primary" style={{ width: `${(s.score / top) * 100}%` }} />
                  </span>
                  {s.score.toFixed(2)}
                </span>
              )}
            </div>
            {s.chunkText && <p className="mt-1 whitespace-pre-line pl-5 text-muted-foreground">{s.chunkText}</p>}
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
  const rootRef = useRef<HTMLDivElement>(null);

  if (message.role === "user") {
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-xl bg-primary px-4 py-3 text-base text-primary-foreground sm:text-sm">
          {message.content}
        </div>
        <div className="hidden size-8 shrink-0 items-center justify-center rounded-lg bg-muted sm:flex">
          <User className="size-4 text-muted-foreground" aria-hidden />
        </div>
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

  return (
    <div ref={rootRef} className="flex gap-3">
      <div className="hidden size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary sm:flex">
        <Bot className="size-4" aria-hidden />
      </div>
      <div className="min-w-0 max-w-full flex-1 space-y-3 sm:max-w-[85%]">
        {message.isStreaming && !message.content && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {message.statusDetail ?? "Thinking…"}
          </p>
        )}

        {message.content && (
          <div className="prose prose-sm max-w-none break-words rounded-xl bg-muted px-4 py-3 text-base dark:prose-invert sm:text-sm">
            <Markdown
              renderCitation={(n) =>
                sources[n - 1] ? (
                  <CitationChip n={n} source={sources[n - 1]} claims={claimsFor(n)} onShowInPanel={() => showInPanel(n)} />
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

        {done && (message.grounded !== undefined || message.citations?.confidence || message.rewrite) && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {message.grounded === true && (
              <Badge variant="success">
                <ShieldCheck aria-hidden /> Checked against sources
              </Badge>
            )}
            {message.grounded === false && (
              <Badge variant="warning">
                <ShieldAlert aria-hidden /> Not fully supported by sources
              </Badge>
            )}
            {message.citations?.confidence && (
              <Badge variant="outline">Confidence: {message.citations.confidence}</Badge>
            )}
            {message.rewrite && message.rewrite.rewritten !== message.rewrite.original && (
              <span className="text-muted-foreground">Searched for “{message.rewrite.rewritten}”</span>
            )}
          </div>
        )}

        {sources.length > 0 && (
          <SourcesPanel id={message.id} sources={sources} open={panelOpen} onToggle={setPanelOpen} />
        )}

        {done && (
          <div className="flex items-center gap-0.5 text-muted-foreground">
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
            className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center"
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
    </div>
  );
}
