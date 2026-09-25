"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertCircle,
  Bot,
  Check,
  Copy,
  FileText,
  Loader2,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  User,
} from "lucide-react";
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

function SourceChip({ source, n, claims }: { source: QuerySource; n: number; claims: string[] }) {
  const name = source.documentName ?? "Unknown document";
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex max-w-full items-center gap-1.5 rounded-md border bg-background px-2 py-1 text-xs transition-colors hover:bg-accent"
          aria-label={`Source ${n}: ${name}${source.page ? `, page ${source.page}` : ""}`}
        >
          <span className="font-semibold text-primary">{n}</span>
          <span className="truncate">{name}</span>
          {source.page ? <span className="text-muted-foreground">p.{source.page}</span> : null}
        </button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex items-start gap-2">
          <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0">
            <p className="break-words font-medium">{name}</p>
            <p className="text-xs text-muted-foreground">
              {[source.page && `Page ${source.page}`, source.heading || source.section]
                .filter(Boolean)
                .join(" · ")}
              {source.score !== undefined && ` · relevance ${source.score.toFixed(2)}`}
            </p>
          </div>
        </div>
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
      </PopoverContent>
    </Popover>
  );
}

interface ChatMessageProps {
  message: Message;
  onRegenerate?: () => void;
  onFeedback?: (value: "up" | "down") => void;
}

export function ChatMessage({ message, onRegenerate, onFeedback }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-xl bg-primary px-4 py-3 text-sm text-primary-foreground">
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

  const copy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex gap-3">
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
          <div className="prose prose-sm max-w-none break-words rounded-xl bg-muted px-4 py-3 text-sm dark:prose-invert">
            <Markdown>{message.content}</Markdown>
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
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">Sources</p>
            <div className="flex flex-wrap gap-1.5">
              {sources.map((s, i) => (
                <SourceChip key={s.chunkId ?? i} source={s} n={i + 1} claims={claimsFor(i + 1)} />
              ))}
            </div>
          </div>
        )}

        {done && (
          <div className="flex items-center gap-0.5 text-muted-foreground">
            {message.content && (
              <Button variant="ghost" size="icon" className="size-8" aria-label={copied ? "Copied" : "Copy answer"} onClick={copy}>
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              </Button>
            )}
            {onRegenerate && (
              <Button variant="ghost" size="icon" className="size-8" aria-label="Regenerate answer" onClick={onRegenerate}>
                <RotateCcw className="size-3.5" />
              </Button>
            )}
            {onFeedback && message.content && !message.error && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn("size-8", message.feedback === "up" && "text-primary")}
                  aria-label="Good answer"
                  aria-pressed={message.feedback === "up"}
                  onClick={() => onFeedback("up")}
                >
                  <ThumbsUp className="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn("size-8", message.feedback === "down" && "text-destructive")}
                  aria-label="Bad answer"
                  aria-pressed={message.feedback === "down"}
                  onClick={() => onFeedback("down")}
                >
                  <ThumbsDown className="size-3.5" />
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
