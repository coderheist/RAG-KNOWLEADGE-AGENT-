export type DocumentStatus = "indexed" | "processing" | "failed" | "already_exists";

export interface Document {
  id: string;
  name: string;
  type: string;
  size: number;
  chunks: number;
  status: DocumentStatus;
  uploadedAt: Date;
  collectionId?: string;
  error?: string;
}

export interface DashboardStats {
  totalDocuments: number;
  totalChunks: number;
  storageUsed: number;
  storageLimit: number;
}

export interface Collection {
  id: string;
  name: string;
  documentCount: number;
  createdAt: Date;
}

export interface QuerySource {
  documentId?: string;
  documentName?: string;
  chunkText?: string;
  page?: number;
  score?: number;
  chunkId?: string;
  heading?: string;
  section?: string;
  /** Cross-encoder score, present only when reranking is enabled on the backend. */
  rerankScore?: number;
}

/** What the agent is doing right now, shown while an answer streams. */
export type ChatStatus =
  | "idle"
  | "thinking"
  | "searching"
  | "generating"
  | "complete"
  | "error";

export interface CitationClaim {
  text: string;
  sourceIds: number[];
}

export interface CitationInfo {
  claims: CitationClaim[];
  confidence?: "high" | "medium" | "low";
  droppedSourceIds: number;
  invalidInline: { filename: string; page: number }[];
}

export interface HealthInfo {
  status: string;
  gemini: string;
  qdrant: string;
  postgres: string;
  backend: string;
  environment: string;
  version?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: QuerySource[];
  isStreaming?: boolean;
  error?: string;
  status?: ChatStatus;
  /** Human-readable description of the current step, e.g. "Searching for: ...". */
  statusDetail?: string;
  /** The question this answer responds to, kept so it can be regenerated. */
  question?: string;
  rewrite?: { original: string; rewritten: string };
  /** true/false once the backend's groundedness check ran; null if the check itself failed. */
  grounded?: boolean | null;
  citations?: CitationInfo;
  timingsMs?: Record<string, number>;
  feedback?: "up" | "down";
}
export const suggestedQuestions = [
  "What documents are in my knowledge base?",
  "Summarize the key points from my uploaded files.",
  "What are the main topics covered?",
  "Find information about product requirements.",
];
