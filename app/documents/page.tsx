import { AppShell } from "@/components/layout/app-shell";
import { DocumentsList } from "@/components/documents/documents-list";

export default function DocumentsPage() {
  return (
    <AppShell activePath="/documents">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Documents</h1>
        <p className="mt-2 text-muted-foreground">Everything in your library. Deleting a file also removes it from answers.</p>
      </div>

      <DocumentsList />
    </AppShell>
  );
}
