"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { useTheme } from "next-themes";

const pages = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Upload documents", href: "/dashboard#upload" },
  { label: "Documents", href: "/documents" },
  { label: "Collections", href: "/collections" },
  { label: "Chat", href: "/chat" },
  { label: "Settings", href: "/settings" },
];

const itemClass =
  "cursor-pointer rounded-md px-3 py-2 text-sm text-foreground aria-selected:bg-accent aria-selected:text-accent-foreground";
const groupClass =
  "text-xs text-muted-foreground [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5";

/** Ctrl/Cmd+K: jump to any page or switch theme. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const run = (fn: () => void) => {
    setOpen(false);
    fn();
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command menu"
      overlayClassName="fixed inset-0 z-50 bg-black/50"
      contentClassName="fixed left-1/2 top-[20%] z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lg"
    >
      <Command.Input
        placeholder="Go to a page or run a command…"
        className="w-full border-b bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
      />
      <Command.List className="max-h-80 overflow-y-auto p-2">
        <Command.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">No results.</Command.Empty>
        <Command.Group heading="Pages" className={groupClass}>
          {pages.map((p) => (
            <Command.Item key={p.href} className={itemClass} onSelect={() => run(() => router.push(p.href))}>
              {p.label}
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Appearance" className={groupClass}>
          <Command.Item
            className={itemClass}
            onSelect={() => run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))}
          >
            Toggle dark mode
          </Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
