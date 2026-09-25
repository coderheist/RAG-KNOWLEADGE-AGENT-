"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bot, Plus, Send, Square, Upload } from "lucide-react";
import { toast } from "sonner";
import { getDocuments } from "@/lib/api/documents";
import { streamQuery } from "@/lib/api/query";
import { useApp } from "@/lib/context/app-context";
import { suggestedQuestions, type ChatMessage as Message, type Document } from "@/lib/types";
import { ChatMessage } from "@/components/chat/chat-message";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function EmptyState({ documents, onAsk }: { documents: Document[] | null; onAsk: (q: string) => void }) {
  if (documents === null) {
    return (
      <div className="mx-auto w-full max-w-md space-y-3" aria-hidden>
        <Skeleton className="mx-auto size-14 rounded-2xl" />
        <Skeleton className="mx-auto h-4 w-48" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  const indexed = documents.filter((d) => d.status === "indexed");
  if (indexed.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Upload className="size-7" aria-hidden />
        </div>
        <div>
          <p className="font-medium">No documents yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Upload a document and ask questions about it here.</p>
        </div>
        <Button asChild>
          <Link href="/dashboard#upload">Upload documents</Link>
        </Button>
      </div>
    );
  }

  const questions = [
    ...indexed.slice(0, 3).map((d) => `Summarize the key points of ${d.name}.`),
    ...suggestedQuestions,
  ].slice(0, 4);

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <Bot className="size-7" aria-hidden />
      </div>
      <div>
        <p className="font-medium">Ask about your documents</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {indexed.length} indexed document{indexed.length === 1 ? "" : "s"} ready to search
        </p>
      </div>
      <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
        {questions.map((q) => (
          <Button
            key={q}
            variant="outline"
            className="h-auto justify-start whitespace-normal px-3 py-2 text-left text-sm font-normal"
            onClick={() => onAsk(q)}
          >
            {q}
          </Button>
        ))}
      </div>
    </div>
  );
}

export function ChatInterface() {
  const { activeCollectionId, refreshKey } = useApp();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [liveStatus, setLiveStatus] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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

  // ponytail: feedback is kept client-side until the /feedback endpoint lands (Phase 6).
  const giveFeedback = (id: string, value: "up" | "down") =>
    patch(id, (m) => ({ feedback: m.feedback === value ? undefined : value }));

  return (
    <Card className="flex h-[calc(100dvh-20rem)] min-h-[24rem] flex-col gap-0 overflow-hidden p-0 md:h-[calc(100dvh-12rem)]">
      <div className="flex items-center justify-between border-b border-border/60 px-4 py-2 sm:px-6">
        <p className="text-sm text-muted-foreground">
          {conversationId ? "Follow-up questions remember this conversation" : "New conversation"}
        </p>
        <Button variant="ghost" size="sm" onClick={newChat} disabled={messages.length === 0}>
          <Plus className="size-4" aria-hidden /> New chat
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6" aria-label="Conversation" role="log">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <EmptyState documents={documents} onAsk={(q) => sendQuery(q)} />
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((m) => (
              <ChatMessage
                key={m.id}
                message={m}
                onRegenerate={m.role === "assistant" && m.question && !isStreaming ? () => sendQuery(m.question!, m.id) : undefined}
                onFeedback={(v) => giveFeedback(m.id, v)}
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
        className="border-t border-border/60 p-3 sm:p-4"
        onSubmit={(e) => {
          e.preventDefault();
          sendQuery(input);
        }}
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your documents…"
            aria-label="Your question"
            className="max-h-40 min-h-[44px] resize-none [field-sizing:content]"
            rows={1}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                sendQuery(input);
              }
            }}
          />
          {isStreaming ? (
            <Button type="button" variant="outline" size="icon" aria-label="Stop generating" onClick={stopGeneration}>
              <Square className="size-4" />
            </Button>
          ) : (
            <Button type="submit" size="icon" aria-label="Send question" disabled={!input.trim()}>
              <Send className="size-4" />
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
