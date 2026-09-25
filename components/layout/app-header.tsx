import { Brain, LayoutDashboard, FileStack, MessageSquare, Settings } from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Documents", href: "/documents", icon: FileStack },
  { label: "Chat", href: "/chat", icon: MessageSquare },
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
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Brain className="size-4" aria-hidden />
          </div>
          <span className="text-lg font-semibold tracking-tight">RAG Agent</span>
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
