import { FileStack, FolderTree, LayoutDashboard, MessageSquare, Settings } from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Documents", href: "/documents", icon: FileStack },
  { label: "Collections", href: "/collections", icon: FolderTree },
  { label: "Settings", href: "/settings", icon: Settings },
];

function NavLinks({ activePath, compact }: { activePath: string; compact?: boolean }) {
  return navItems.map((item) => {
    const isActive =
      activePath === item.href ||
      (item.href !== "/dashboard" && activePath.startsWith(item.href));

    return (
      <Link
        key={item.label}
        href={item.href}
        aria-current={isActive ? "page" : undefined}
        className={cn(
          "flex items-center gap-2 rounded-lg text-sm font-medium transition-colors",
          compact ? "flex-1 flex-col gap-1 px-2 py-1.5 text-xs" : "px-3 py-2",
          isActive
            ? "bg-primary/10 text-primary"
            : "text-muted-foreground hover:bg-muted hover:text-foreground"
        )}
      >
        <item.icon className="size-4" aria-hidden />
        {item.label}
      </Link>
    );
  });
}

export function AppHeader({ activePath }: { activePath: string }) {
  return (
    <header className="sticky top-0 z-50 border-b bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/dashboard" className="rounded-sm text-[17px] font-semibold tracking-tight" aria-label="RAG Agent, home">
          {/* The brand is the product's one idea: a highlighter stroke over evidence. */}
          <span className="bg-[linear-gradient(transparent_58%,var(--highlight)_58%)] px-0.5">RAG Agent</span>
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          <NavLinks activePath={activePath} />
        </nav>

        <ThemeToggle />
      </div>

      <nav aria-label="Main mobile" className="flex gap-1 border-t border-border/60 px-2 py-1.5 md:hidden">
        <NavLinks activePath={activePath} compact />
      </nav>
    </header>
  );
}
