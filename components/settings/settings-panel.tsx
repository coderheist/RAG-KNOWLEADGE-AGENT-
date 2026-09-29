"use client";

import { useEffect, useState } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { getApiBase } from "@/lib/api/client";
import { useHealth } from "@/lib/hooks/use-health";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type State = "connected" | "unavailable" | "checking";

function stateOf(raw: string | undefined): State {
  const s = String(raw ?? "").toLowerCase();
  if (["connected", "ok", "healthy", "true"].some((w) => s.includes(w))) return "connected";
  if (!s || s === "unknown") return "checking";
  return "unavailable";
}

const LABEL: Record<State, string> = { connected: "Connected", unavailable: "Unavailable", checking: "Checking" };

const services = [
  { key: "backend", label: "API server", role: "Answers questions and indexes files" },
  { key: "gemini", label: "Google Gemini", role: "Embeddings and answers" },
  { key: "qdrant", label: "Qdrant", role: "Passage search" },
  { key: "postgres", label: "PostgreSQL", role: "Documents, conversations and feedback" },
] as const;

export function SettingsPanel() {
  const { health, loading, error, refetch } = useHealth();
  const [urlInput, setUrlInput] = useState("");

  useEffect(() => {
    setUrlInput(getApiBase());
  }, []);

  const handleSaveUrl = () => {
    if (!urlInput.trim()) return;
    localStorage.setItem("rag_backend_url", urlInput.trim());
    toast.success("API address saved");
    refetch();
  };

  return (
    <div className="grid max-w-3xl gap-6">
      {error && (
        <p className="flex items-center gap-2 rounded-lg border border-destructive/30 px-4 py-3 text-sm text-destructive" role="alert">
          <AlertCircle className="size-4 shrink-0" aria-hidden />
          Could not reach the API: {error}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Services</CardTitle>
          <CardDescription>Everything an answer depends on.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="divide-y border-y">
            {services.map((service) => {
              const state = stateOf(health?.[service.key]?.toString());
              return (
                <div key={service.key} className="flex items-center justify-between gap-4 py-3">
                  <dt className="min-w-0">
                    <span className="block text-sm font-medium">{service.label}</span>
                    <span className="block text-xs text-muted-foreground">{service.role}</span>
                  </dt>
                  <dd className="flex shrink-0 items-center gap-2 text-sm">
                    {loading ? (
                      <Skeleton className="h-5 w-24" />
                    ) : (
                      <>
                        <span
                          aria-hidden
                          className={cn(
                            "size-2 rounded-full",
                            state === "connected" && "bg-success",
                            state === "unavailable" && "bg-destructive",
                            state === "checking" && "bg-warning"
                          )}
                        />
                        <span className={state === "unavailable" ? "text-destructive" : undefined}>{LABEL[state]}</span>
                      </>
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>
          <Button variant="outline" size="sm" className="mt-4" onClick={refetch} disabled={loading}>
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} aria-hidden /> Check again
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Connection</CardTitle>
          <CardDescription>Where this app sends requests. The default works when the API runs alongside it.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5 text-sm">
          <div className="space-y-2">
            <label htmlFor="api-url" className="font-medium">
              API address
            </label>
            <div className="flex max-w-md gap-2">
              <Input id="api-url" value={urlInput} onChange={(e) => setUrlInput(e.target.value)} placeholder="http://localhost:8000" />
              <Button onClick={handleSaveUrl}>Save</Button>
            </div>
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-8 gap-y-2">
            <dt className="text-muted-foreground">Environment</dt>
            <dd>{loading ? <Skeleton className="h-4 w-24" /> : health?.environment ?? "Unknown"}</dd>
            {health?.version && (
              <>
                <dt className="text-muted-foreground">Version</dt>
                <dd>{health.version}</dd>
              </>
            )}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
