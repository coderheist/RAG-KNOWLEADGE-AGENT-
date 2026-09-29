"use client";

import { useState } from "react";
import {
  AlertCircle,
  Clock,
  FileSpreadsheet,
  FileText,
  FileType,
  Loader2,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { deleteDocument } from "@/lib/api/documents";
import { useApp } from "@/lib/context/app-context";
import { useDocuments } from "@/lib/hooks/use-documents";
import type { DocumentStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatBytes, formatRelativeTime } from "@/lib/utils";

const typeIcons: Record<string, typeof FileText> = {
  PDF: FileText,
  Markdown: FileType,
  Spreadsheet: FileSpreadsheet,
  Document: FileText,
  Text: FileType,
};

const statusConfig: Record<
  DocumentStatus,
  { label: string; variant: "success" | "warning" | "destructive" }
> = {
  indexed: { label: "Indexed", variant: "success" },
  processing: { label: "Processing", variant: "warning" },
  failed: { label: "Failed", variant: "destructive" },
  already_exists: { label: "Already Indexed", variant: "success" },
};

const PAGE_SIZE = 25;

export function DocumentsList() {
  const { refresh } = useApp();
  const { documents, setDocuments, loading, error } = useDocuments({
    pollProcessing: true,
  });
  const [deletingId, setDeletingId] = useState<string | null>(null);
  // Render in pages: all rows at once (each with its own dialog) blocked the main thread for >2 s on mobile.
  const [visible, setVisible] = useState(PAGE_SIZE);

  // Optimistic: the row disappears at once and comes back if the API refuses.
  const handleDelete = async (id: string, name: string) => {
    const previous = documents;
    setDeletingId(id);
    setDocuments(previous.filter((d) => d.id !== id));
    try {
      await deleteDocument(id);
      toast.success(`Deleted ${name} and its indexed chunks`);
      refresh();
    } catch (err) {
      setDocuments(previous);
      toast.error(`Could not delete ${name}: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>All Documents</CardTitle>
        <CardDescription>
          Manage uploaded files and indexing status
        </CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        {error ? (
          <div className="flex items-center gap-3 px-6 py-8 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : loading ? (
          <div className="space-y-4 px-6 py-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="size-10 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
              </div>
            ))}
          </div>
        ) : documents.length === 0 ? (
          <p className="px-6 py-8 text-center text-sm text-muted-foreground">
            No documents uploaded yet.
          </p>
        ) : (
          <ul className="divide-y divide-border/60">
            {documents.slice(0, visible).map((doc) => {
              const Icon = typeIcons[doc.type] ?? FileText;
              const status = statusConfig[doc.status];

              return (
                <li
                  key={doc.id}
                  className="flex items-center gap-4 px-6 py-4 transition-colors hover:bg-muted/40"
                >
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <Icon className="size-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{doc.name}</p>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      <span>{doc.type}</span>
                      <span>{formatBytes(doc.size)}</span>
                      <span>{doc.chunks} chunk{doc.chunks === 1 ? "" : "s"}</span>
                      <span className="flex items-center gap-1">
                        <Clock className="size-3" />
                        {formatRelativeTime(doc.uploadedAt)}
                      </span>
                    </div>
                  </div>
                  <Badge variant={status.variant}>{status.label}</Badge>
                  <ConfirmDelete
                    title={`Delete "${doc.name}"?`}
                    description="The document and its indexed chunks are removed. Answers will no longer cite it."
                    onConfirm={() => handleDelete(doc.id, doc.name)}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${doc.name}`}
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                      disabled={deletingId === doc.id}
                    >
                      {deletingId === doc.id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Trash2 className="size-4" />
                      )}
                    </Button>
                  </ConfirmDelete>
                </li>
              );
            })}
            {documents.length > visible && (
              <li className="flex items-center justify-between px-6 py-3 text-sm text-muted-foreground">
                <span>
                  Showing {visible} of {documents.length}
                </span>
                <Button variant="outline" size="sm" onClick={() => setVisible((v) => v + PAGE_SIZE)}>
                  Show more
                </Button>
              </li>
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
