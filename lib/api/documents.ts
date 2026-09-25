import { apiFetch } from "@/lib/api/client";
import { normalizeDocumentsPayload } from "@/lib/api/normalize";
import type { DashboardStats, Document } from "@/lib/types";

export async function getDocuments(collectionId?: string | null): Promise<{
  documents: Document[];
  stats: DashboardStats;
}> {
  // The API pages at <=100 items; fetch every page so lists and totals are complete.
  const documents: Document[] = [];
  let stats: DashboardStats | undefined;
  for (let page = 1; ; page++) {
    const params = new URLSearchParams({ page: String(page), limit: "100" });
    if (collectionId) params.set("collection_id", collectionId);
    const raw = await apiFetch<{ pages?: number }>(`/documents?${params}`);
    const batch = normalizeDocumentsPayload(raw);
    documents.push(...batch.documents);
    stats ??= batch.stats;
    if (page >= (raw?.pages ?? 1)) break;
  }
  return {
    documents,
    stats: {
      ...stats!,
      totalChunks: documents.reduce((sum, d) => sum + d.chunks, 0),
      storageUsed: documents.reduce((sum, d) => sum + d.size, 0),
    },
  };
}

export async function deleteDocument(id: string): Promise<void> {
  await apiFetch<void>(`/documents/${id}`, { method: "DELETE" });
}

export async function assignDocumentToCollection(
  documentId: string,
  collectionId: string | null
): Promise<void> {
  await apiFetch(`/documents/${documentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ collection_id: collectionId }),
  });
}
