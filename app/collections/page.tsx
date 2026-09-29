import { AppShell } from "@/components/layout/app-shell";
import { CollectionsManager } from "@/components/collections/collections-manager";

export default function CollectionsPage() {
  return (
    <AppShell activePath="/collections">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Collections</h1>
        <p className="mt-2 max-w-[62ch] text-muted-foreground">
          Group documents so a question searches only the set you choose. The collection in use applies to chat.
        </p>
      </div>

      <CollectionsManager />
    </AppShell>
  );
}
