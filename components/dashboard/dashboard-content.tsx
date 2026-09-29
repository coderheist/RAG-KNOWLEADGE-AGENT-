"use client";

import Link from "next/link";
import { MessageSquare } from "lucide-react";
import { HealthStatus } from "@/components/dashboard/health-status";
import { RecentDocuments } from "@/components/dashboard/recent-documents";
import { UploadCard } from "@/components/dashboard/upload-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments } from "@/lib/hooks/use-documents";
import { formatBytes } from "@/lib/utils";

export function DashboardContent() {
  const { documents, stats, loading, error, refetch } = useDocuments({ pollProcessing: true });
  const plural = (n: number, word: string) => `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;

  return (
    <div className="space-y-10">
      <section className="flex flex-col gap-6 border-b pb-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight">Your library</h1>
          {loading ? (
            <Skeleton className="mt-3 h-5 w-80" />
          ) : error ? (
            <p className="mt-2 text-destructive">Could not load your documents: {error}</p>
          ) : (
            <p className="mt-2 max-w-[62ch] text-muted-foreground">
              {plural(stats.totalDocuments, "document")}, {plural(stats.totalChunks, "indexed passage")},{" "}
              {formatBytes(stats.storageUsed)} of {formatBytes(stats.storageLimit)} used.
            </p>
          )}
          <div className="mt-4">
            <HealthStatus />
          </div>
        </div>
        <Button asChild size="lg" className="self-start lg:self-auto">
          <Link href="/chat">
            <MessageSquare className="size-4" aria-hidden /> Ask a question
          </Link>
        </Button>
      </section>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <UploadCard disabled={false} onUploadComplete={refetch} />
        <RecentDocuments documents={documents} loading={loading} error={error} />
      </div>
    </div>
  );
}
