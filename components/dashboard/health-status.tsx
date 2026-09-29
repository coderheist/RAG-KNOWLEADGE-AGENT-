"use client";

import { RefreshCw } from "lucide-react";
import { useHealth } from "@/lib/hooks/use-health";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type State = "online" | "offline" | "checking";

function stateOf(value: string | undefined): State {
  const s = String(value ?? "").toLowerCase();
  if (["connected", "ok", "healthy"].includes(s)) return "online";
  if (["not_connected", "disconnected", "failed", "error"].includes(s)) return "offline";
  return "checking";
}

/** One quiet line: a dot per service, and words only when something needs attention. */
export function HealthStatus() {
  const { health, loading, refetch } = useHealth();

  const services = [
    { name: "API", value: health?.backend },
    { name: "Gemini", value: health?.gemini },
    { name: "Postgres", value: health?.postgres },
    { name: "Qdrant", value: health?.qdrant },
  ].map((s) => ({ ...s, state: stateOf(s.value) }));
  const allOnline = services.every((s) => s.state === "online");

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
      <span className="sr-only">Service status: </span>
      {services.map((s) => (
        <span key={s.name} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn(
              "size-2 rounded-full",
              s.state === "online" && "bg-success",
              s.state === "offline" && "bg-destructive",
              s.state === "checking" && "bg-warning"
            )}
          />
          {s.name}
          {s.state !== "online" && (
            <span className={s.state === "offline" ? "text-destructive" : undefined}>
              {s.state === "offline" ? "offline" : "checking"}
            </span>
          )}
          <span className="sr-only">{s.state === "online" ? "online" : ""}</span>
        </span>
      ))}
      {!allOnline && !loading && (
        <Button variant="ghost" size="sm" className="h-7 px-2" onClick={refetch}>
          <RefreshCw className="size-3.5" aria-hidden /> Check again
        </Button>
      )}
    </div>
  );
}
