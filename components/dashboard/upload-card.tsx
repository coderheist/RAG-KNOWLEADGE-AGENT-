"use client";

import { useCallback, useRef, useState } from "react";
import { FileUp, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { uploadDocuments } from "@/lib/api/upload";
import { useApp } from "@/lib/context/app-context";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface UploadCardProps {
  disabled?: boolean;
  onUploadComplete?: () => void;
}

export function UploadCard({ disabled, onUploadComplete }: UploadCardProps) {
  const { activeCollectionId, refresh } = useApp();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processing, setProcessing] = useState(false);

  const isDisabled = disabled || uploading || processing;

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.xlsx', '.csv', '.txt', '.md', '.markdown', '.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp', '.json', '.log'];
      const uploadableFiles = Array.from(files).filter((file) => {
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        return ALLOWED_EXTENSIONS.includes(ext);
      });

      if (uploadableFiles.length === 0) {
        toast.error("Please upload supported document formats only (.pdf, .docx, .pptx, .xlsx, .csv, .txt, .md, .markdown, .png, .jpg, .jpeg, .tiff, .bmp, .webp, .json, .log).");
        return;
      }

      setUploading(true);
      setUploadProgress(0);

      let slowUploadTimer: NodeJS.Timeout | null = null;
      let toastId: string | number | null = null;

      slowUploadTimer = setTimeout(() => {
        toastId = toast.loading(
          "Embedding document... Large documents may take several minutes because embeddings are being generated.",
          { duration: Infinity }
        );
      }, 5000);

      try {
        const results = await uploadDocuments(uploadableFiles, {
          collectionId: activeCollectionId,
          onProgress: ({ progress }) => setUploadProgress(progress),
        });

        if (slowUploadTimer) clearTimeout(slowUploadTimer);
        if (toastId) toast.dismiss(toastId);

        setUploading(false);
        setProcessing(true);

        const alreadyExistsCount = results.filter((doc) => doc.status === "already_exists").length;
        const succeededCount = results.filter((doc) => doc.status === "indexed" || doc.status === "processing").length;
        const failedDocs = results.filter((doc) => doc.status === "failed");

        if (failedDocs.length > 0) {
          const errMsg = failedDocs
            .map((doc) => `${doc.name}: ${doc.error || "Processing failed"}`)
            .join(", ");
          if (succeededCount > 0) {
            toast.success(`${succeededCount} files uploaded successfully`);
          }
          throw new Error(errMsg);
        }

        // Say what happened to each file, e.g. "Indexed pricing.xlsx · 142 chunks".
        const describe = (doc: (typeof results)[number]) =>
          doc.status === "already_exists"
            ? `${doc.name} is already indexed`
            : doc.status === "processing"
              ? `Processing ${doc.name}…`
              : `Indexed ${doc.name} · ${doc.chunks} chunk${doc.chunks === 1 ? "" : "s"}`;
        const lines = results.map(describe);
        const notify = alreadyExistsCount > 0 && succeededCount === 0 ? toast.info : toast.success;
        if (lines.length === 1) notify(lines[0]);
        else notify(`${succeededCount} of ${results.length} files indexed`, { description: lines.join(" · ") });

        refresh();
        onUploadComplete?.();
      } catch (err) {
        if (slowUploadTimer) clearTimeout(slowUploadTimer);
        if (toastId) toast.dismiss(toastId);
        toast.error(
          err instanceof Error ? err.message : "Upload failed"
        );
      } finally {
        setUploading(false);
        setProcessing(false);
        setUploadProgress(0);
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [activeCollectionId, onUploadComplete, refresh]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!isDisabled) setIsDragging(true);
    },
    [isDisabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (isDisabled || !e.dataTransfer.files.length) return;
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles, isDisabled]
  );

  return (
    <div
      id="upload"
    >
      <Card>
        <CardHeader>
          <CardTitle>Add documents</CardTitle>
          <CardDescription>Each file is split into passages and indexed, so answers can cite it.</CardDescription>
        </CardHeader>
        <CardContent>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.csv,text/csv,.txt,text/plain,.md,text/markdown,.markdown,text/markdown,.png,image/png,.jpg,image/jpeg,.jpeg,image/jpeg,.tiff,image/tiff,.bmp,image/bmp,.webp,image/webp,.json,application/json,.log,text/plain"
            multiple
            className="hidden"
            disabled={isDisabled}
            onChange={(e) => {
              if (e.target.files?.length) handleFiles(e.target.files);
            }}
          />
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed px-6 py-10 text-center transition-colors",
              isDragging ? "border-primary bg-accent" : "border-input hover:border-primary/50",
              isDisabled && "pointer-events-none opacity-60"
            )}
          >
            {uploading || processing ? (
              <Loader2 className="mb-3 size-6 animate-spin text-primary" aria-hidden />
            ) : (
              <FileUp className="mb-3 size-6 text-muted-foreground" aria-hidden />
            )}
            <p className="text-sm font-medium">
              {uploading
                ? `Uploading… ${uploadProgress}%`
                : processing
                  ? "Indexing your documents…"
                  : isDragging
                    ? "Release to add these files"
                    : "Drop files here"}
            </p>
            <p className="mt-1 max-w-[40ch] text-xs text-muted-foreground">
              PDF, Word, PowerPoint, Excel, CSV, Markdown or text, up to 50 MB each. Images are read with OCR.
            </p>
            {(uploading || processing) && (
              <Progress
                aria-label="Upload progress"
                value={uploading ? uploadProgress : undefined}
                className="mt-4 h-1.5 w-full max-w-xs"
              />
            )}
            <Button className="mt-5" variant="outline" size="sm" disabled={isDisabled} onClick={() => inputRef.current?.click()}>
              Choose files
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
