import { AppHeader } from "@/components/layout/app-header";
import { CommandPalette } from "@/components/layout/command-palette";

export function AppShell({
  activePath,
  children,
  flush = false,
}: {
  activePath: string;
  children: React.ReactNode;
  /** No vertical padding: for full-height screens such as chat. */
  flush?: boolean;
}) {
  return (
    <div className="min-h-screen bg-background">
      <AppHeader activePath={activePath} />
      <CommandPalette />

      <main className={`relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 ${flush ? "" : "py-8"}`}>
        {children}
      </main>
    </div>
  );
}
