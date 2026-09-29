"use client";

import { useState } from "react";
import {
  AlertCircle,
  Check,
  FolderOpen,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { assignDocumentToCollection } from "@/lib/api/documents";
import {
  createCollection,
  deleteCollection,
} from "@/lib/api/collections";
import { useApp } from "@/lib/context/app-context";
import { useCollections } from "@/lib/hooks/use-collections";
import { useDocuments } from "@/lib/hooks/use-documents";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function CollectionsManager() {
  const { activeCollectionId, setActiveCollectionId, refresh } = useApp();
  const {
    collections,
    loading: collectionsLoading,
    error: collectionsError,
    refetch: refetchCollections,
  } = useCollections();
  const { documents, loading: documentsLoading, refetch: refetchDocuments } =
    useDocuments();
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [assigningId, setAssigningId] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const collection = await createCollection(newName.trim());
      toast.success(`Collection "${collection.name}" created`);
      setNewName("");
      setDialogOpen(false);
      refresh();
      refetchCollections();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteCollection = async (id: string, name: string) => {
    setDeletingId(id);
    try {
      await deleteCollection(id);
      if (activeCollectionId === id) setActiveCollectionId(null);
      toast.success(`Collection "${name}" deleted`);
      refresh();
      refetchCollections();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };

  const handleAssign = async (documentId: string, collectionId: string | null) => {
    setAssigningId(documentId);
    try {
      await assignDocumentToCollection(documentId, collectionId);
      toast.success("Document assigned");
      refresh();
      refetchDocuments();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Assign failed");
    } finally {
      setAssigningId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="size-4" aria-hidden />
              New collection
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New collection</DialogTitle>
              <DialogDescription>
                Group related documents, then ask questions that search only that group.
              </DialogDescription>
            </DialogHeader>
            <div className="flex gap-2">
              <Input
                placeholder="Collection name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
              <Button disabled={creating || !newName.trim()} onClick={handleCreate}>
                {creating ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  "Create"
                )}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {collectionsError && (
        <div className="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          <span>{collectionsError}</span>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {collectionsLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))
        ) : collections.length === 0 ? (
          <Card className="sm:col-span-2 lg:col-span-3">
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              No collections yet. Create one to organize your documents.
            </CardContent>
          </Card>
        ) : (
          collections.map((collection, index) => {
            const isActive = activeCollectionId === collection.id;
            return (
              <div
                key={collection.id}
              >
                <Card
                  className={cn(
                    "transition-colors",
                    isActive && "border-primary ring-1 ring-primary/30"
                  )}
                >
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <FolderOpen className="size-4" />
                        </div>
                        <div>
                          <CardTitle className="text-base">
                            {collection.name}
                          </CardTitle>
                          <CardDescription>
                            {collection.documentCount} document{collection.documentCount === 1 ? "" : "s"}
                          </CardDescription>
                        </div>
                      </div>
                      {isActive && (
                        <Badge variant="success">
                          <Check className="size-3" aria-hidden />
                          In use
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1"
                      onClick={() =>
                        setActiveCollectionId(isActive ? null : collection.id)
                      }
                    >
                      {isActive ? "Search all documents" : "Search only this collection"}
                    </Button>
                    <ConfirmDelete
                      title={`Delete collection "${collection.name}"?`}
                      description="This permanently deletes the collection and every indexed chunk stored in it. It cannot be undone."
                      onConfirm={() => handleDeleteCollection(collection.id, collection.name)}
                    >
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Delete collection ${collection.name}`}
                        className="text-muted-foreground hover:text-destructive"
                        disabled={deletingId === collection.id}
                      >
                        {deletingId === collection.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Trash2 className="size-4" />
                        )}
                      </Button>
                    </ConfirmDelete>
                  </CardContent>
                </Card>
              </div>
            );
          })
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Assign documents</CardTitle>
          <CardDescription>Choose which collection each document belongs to.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {documentsLoading ? (
            <div className="space-y-3 px-6">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : documents.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-muted-foreground">
              Upload documents first to assign them to collections.
            </p>
          ) : (
            <ul className="divide-y">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="flex flex-col gap-3 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <label htmlFor={`coll-${doc.id}`} className="min-w-0 truncate text-sm font-medium">
                    {doc.name}
                  </label>
                  <select
                    id={`coll-${doc.id}`}
                    value={doc.collectionId ?? ""}
                    disabled={assigningId === doc.id}
                    onChange={(e) => handleAssign(doc.id, e.target.value || null)}
                    className="h-11 w-full rounded-md border bg-background px-2 text-sm sm:h-9 sm:w-64"
                  >
                    <option value="">Not in a collection</option>
                    {collections.map((collection) => (
                      <option key={collection.id} value={collection.id}>
                        {collection.name}
                      </option>
                    ))}
                  </select>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
