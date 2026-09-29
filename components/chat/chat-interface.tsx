"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUp, CornerDownRight, Plus, Square, Upload } from "lucide-react";
import { toast } from "sonner";
import { getDocuments } from "@/lib/api/documents";
import { sendFeedback } from "@/lib/api/feedback";
import { uploadDocuments } from "@/lib/api/upload";
import { streamQuery } from "@/lib/api/query";
import { useApp } from "@/lib/context/app-context";
import { suggestedQuestions, type ChatMessage as Message, type Document } from "@/lib/types";
import { ChatMessage } from "@/components/chat/chat-message";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function EmptyState({ documents, onAsk }: { documents: Document[] | null; onAsk: (q: string) => void }) {
  if (documents === null) {
    return (
      <div className="w-full max-w-[68ch] space-y-3" aria-hidden>
        <Skeleton className="h-7 w-80" />
        <Skeleton className="h-4 w-96" />
        <Skeleton className="mt-8 h-11 w-full" />
        <Skeleton className="h-11 w-full" />
      </div>
    );
  }

  const indexed = documents.filter((d) => d.status === "indexed");
  if (indexed.length === 0) {
    return (
      <div className="max-w-[68ch]">
        <h2 className="text-2xl font-semibold tracking-tight">Add a document to start asking questions.</h2>
        <p className="mt-2 text-muted-foreground">
          PDFs, Word and Excel files, slides, CSV and plain text all work. Answers cite the passage they come from.
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard#upload">
            <Upload className="size-4" aria-hidden /> Upload documents
          </Link>
        </Button>
      </div>
    );
  }

  const questions = [
    ...indexed.slice(0, 3).map((d) => `Summarize the key points of ${d.name}.`),
    ...suggestedQuestions,
  ].slice(0, 4);

  return (
    <div className="w-full max-w-[68ch]">
      <h2 className="text-2xl font-semibold tracking-tight text-balance">
        Ask anything about your {indexed.length} document{indexed.length === 1 ? "" : "s"}.
      </h2>
      <p className="mt-2 text-muted-foreground">
        Every answer cites the passage it came from and is checked against it, so you can verify it in one click.
      </p>
      <ul className="mt-8 divide-y border-y" aria-label="Example questions">
        {questions.map((q) => (
          <li key={q}>
            <button
              type="button"
              onClick={() => onAsk(q)}
              className="group flex min-h-11 w-full items-center gap-3 py-3 text-left text-[15px] text-foreground transition-colors hover:text-primary focus-visible:text-primary"
            >
              <CornerDownRight className="size-4 shrink-0 text-muted-foreground group-hover:text-primary" aria-hidden />
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ChatInterface() {
  const { activeCollectionId, refreshKey, refresh } = useApp();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [liveStatus, setLiveStatus] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    getDocuments(activeCollectionId)
      .then((r) => setDocuments(r.documents))
      .catch(() => setDocuments([]));
  }, [activeCollectionId, refreshKey]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const patch = (id: string, fn: (m: Message) => Partial<Message>) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...fn(m) } : m)));

  const sendQuery = useCallback(
    async (raw: string, replaceId?: string) => {
      const query = raw.trim();
      if (!query || isStreaming) return;
      // Load the markdown renderer now, while the answer is being prepared: loading it on mount slowed the
      // page's first paint on mobile, and loading it lazily on the first token left a blank bubble.
      void import("@/components/chat/markdown");

      const assistantId = createId();
      const assistant: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        question: query,
        isStreaming: true,
        status: "thinking",
        statusDetail: "Thinking…",
      };

      setMessages((prev) =>
        replaceId
          ? prev.map((m) => (m.id === replaceId ? assistant : m))
          : [...prev, { id: createId(), role: "user", content: query }, assistant]
      );
      setInput("");
      setIsStreaming(true);
      setLiveStatus("Thinking…");
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamQuery({
          query,
          conversationId,
          collectionId: activeCollectionId,
          signal: controller.signal,
          onStatus: (status, detail) => {
            patch(assistantId, () => ({ status, statusDetail: detail }));
            if (detail) setLiveStatus(detail);
          },
          onQueryRewrite: (original, rewritten) => patch(assistantId, () => ({ rewrite: { original, rewritten } })),
          onSources: (sources, timingsMs) => patch(assistantId, () => ({ sources, timingsMs })),
          onToken: (token) => patch(assistantId, (m) => ({ content: m.content + token, status: "generating" })),
          onGroundedness: (grounded) => patch(assistantId, () => ({ grounded })),
          onCitations: (citations) => patch(assistantId, () => ({ citations })),
          onDone: ({ conversationId: id }) => {
            if (id) setConversationId(id);
            patch(assistantId, () => ({ isStreaming: false, status: "complete" }));
            setLiveStatus("Answer complete");
          },
          onError: (error) => {
            patch(assistantId, () => ({ isStreaming: false, status: "error", error: error.message }));
            setLiveStatus("Something went wrong");
          },
        });
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const message = err instanceof Error ? err.message : "Failed to get response";
        toast.error(message);
        patch(assistantId, () => ({ isStreaming: false, status: "error", error: message }));
      } finally {
        // A stopped request settles late; it must not reset a newer one.
        if (abortRef.current === controller) {
          setIsStreaming(false);
          abortRef.current = null;
        }
      }
    },
    [activeCollectionId, conversationId, isStreaming]
  );

  const stopGeneration = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setMessages((prev) => prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false, status: "complete" } : m)));
    setLiveStatus("Stopped");
  };

  const newChat = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setConversationId(null);
    setIsStreaming(false);
    inputRef.current?.focus();
  };

  const upload = (files: File[]) => {
    if (!files.length) return;
    toast.promise(uploadDocuments(files, { collectionId: activeCollectionId }), {
      loading: `Uploading ${files.length === 1 ? files[0].name : `${files.length} files`}…`,
      success: (docs) => {
        refresh();
        return docs.map((d) => (d.status === "already_exists" ? `${d.name} is already indexed` : `Indexed ${d.name} · ${d.chunks} chunk${d.chunks === 1 ? "" : "s"}`)).join(" · ");
      },
      error: (err) => `Upload failed: ${err instanceof Error ? err.message : "unknown error"}`,
    });
  };

  const commands = [
    { name: "/new", hint: "Start a new conversation", run: newChat },
    { name: "/upload", hint: "Upload documents", run: () => fileRef.current?.click() },
  ];
  const slashMatches = /^\/\S*$/.test(input) ? commands.filter((c) => c.name.startsWith(input)) : [];
  const runCommand = (c: (typeof commands)[number]) => {
    setInput("");
    c.run();
  };

  const giveFeedback = async (m: Message, rating: "up" | "down", comment?: string) => {
    patch(m.id, () => ({ feedback: rating }));
    try {
      await sendFeedback({
        rating,
        comment,
        question: m.question ?? "",
        answer: m.content,
        chunkIds: (m.sources ?? []).map((s) => s.chunkId).filter((c): c is string => !!c),
        conversationId,
      });
      toast.success(rating === "up" ? "Thanks for the feedback" : "Thanks. This answer will be reviewed.");
    } catch (err) {
      patch(m.id, () => ({ feedback: undefined }));
      toast.error(`Feedback not saved: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  };

  return (
    <div className="flex h-[calc(100dvh-8.5rem)] min-h-[26rem] flex-col md:h-[calc(100dvh-4rem)]">
      <div className="flex items-center justify-between gap-4 border-b py-3">
        <div className="min-w-0">
          <h1 className="text-base font-semibold">Ask your documents</h1>
          <p className="text-sm text-muted-foreground">
            {conversationId ? "Follow-up questions remember this conversation." : "Answers cite the passages they come from."}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={newChat} disabled={messages.length === 0}>
          <Plus className="size-4" aria-hidden /> New chat
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto py-8" aria-label="Conversation" role="log">
        {messages.length === 0 ? (
          <div className="flex h-full items-center">
            <EmptyState documents={documents} onAsk={(q) => sendQuery(q)} />
          </div>
        ) : (
          <div className="space-y-12">
            {messages.map((m) => (
              <ChatMessage
                key={m.id}
                message={m}
                onRegenerate={m.role === "assistant" && m.question && !isStreaming ? () => sendQuery(m.question!, m.id) : undefined}
                onFeedback={m.role === "assistant" && m.question ? (v, c) => giveFeedback(m, v, c) : undefined}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <p className="sr-only" role="status" aria-live="polite">
        {liveStatus}
      </p>

      <form
        className="relative pb-4 pt-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (slashMatches[0]) runCommand(slashMatches[0]);
          else sendQuery(input);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(Array.from(e.dataTransfer.files));
        }}
      >
        <input
          ref={fileRef}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            upload(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
        {slashMatches.length > 0 && (
          <ul
            role="listbox"
            aria-label="Commands"
            className="absolute bottom-full left-0 mb-2 w-[min(28rem,100%)] rounded-lg border bg-popover p-1 text-sm shadow-lg"
          >
            {slashMatches.map((c, i) => (
              <li key={c.name} role="option" aria-selected={i === 0}>
                <button
                  type="button"
                  onClick={() => runCommand(c)}
                  className={cn("flex w-full gap-3 rounded-md px-3 py-2 text-left hover:bg-accent", i === 0 && "bg-accent")}
                >
                  <span className="font-medium">{c.name}</span>
                  <span className="text-muted-foreground">{c.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div
          className={cn(
            "flex max-w-[68ch] items-end gap-2 rounded-xl border bg-card p-2 shadow-sm transition-colors focus-within:border-primary",
            dragging && "border-primary bg-accent"
          )}
        >
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={dragging ? "Drop files to upload them" : "Ask a question, or type / for commands"}
            aria-label="Your question"
            className="max-h-52 min-h-[44px] resize-none border-0 bg-transparent px-2 text-[15px] shadow-none focus-visible:ring-0 [field-sizing:content]"
            rows={1}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                if (slashMatches[0]) runCommand(slashMatches[0]);
                else sendQuery(input);
              }
            }}
          />
          {isStreaming ? (
            <Button type="button" variant="outline" size="icon" className="size-11 shrink-0 sm:size-10" aria-label="Stop generating" onClick={stopGeneration}>
              <Square className="size-4" />
            </Button>
          ) : (
            <Button type="submit" size="icon" className="size-11 shrink-0 rounded-lg sm:size-10" aria-label="Send question" disabled={!input.trim()}>
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
        <p className="mt-2 hidden max-w-[68ch] text-xs text-muted-foreground sm:block">
          Enter to send, Shift+Enter for a new line. Drop files here to add them to your library.
        </p>
      </form>
    </div>
  );
}
