import { apiFetch } from "@/lib/api/client";

export interface FeedbackInput {
  rating: "up" | "down";
  question: string;
  answer: string;
  chunkIds: string[];
  conversationId?: string | null;
  comment?: string;
}

/** POST /feedback — thumbs-down rows later become eval candidates (backend/scripts/feedback_to_eval.py). */
export async function sendFeedback(input: FeedbackInput): Promise<void> {
  await apiFetch("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rating: input.rating,
      question: input.question,
      answer: input.answer,
      chunk_ids: input.chunkIds,
      conversation_id: input.conversationId ?? undefined,
      comment: input.comment || undefined,
    }),
  });
}
