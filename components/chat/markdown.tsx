"use client";

import { useMemo, useRef, useState, type ComponentProps, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy } from "lucide-react";
import "highlight.js/styles/github-dark.css";

function CodeBlock({ node: _node, ...props }: ComponentProps<"pre"> & { node?: unknown }) {
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(ref.current?.innerText ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group/code relative">
      <pre ref={ref} {...props} />
      <button
        type="button"
        aria-label={copied ? "Copied" : "Copy code"}
        onClick={copy}
        className="absolute right-2 top-2 rounded-md bg-background/80 p-1.5 text-muted-foreground opacity-0 transition-opacity hover:text-foreground focus-visible:opacity-100 group-hover/code:opacity-100"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </div>
  );
}

export function Markdown({
  children,
  renderCitation,
}: {
  children: string;
  /** Renders "[n](#cite-n)" links (see lib/citations.ts) as citation chips. */
  renderCitation?: (n: number) => ReactNode;
}) {
  // The components object must keep its identity across renders: a new `a` component each render would
  // remount every citation chip (closing its popover) whenever the parent re-renders, e.g. on hover.
  const renderRef = useRef(renderCitation);
  renderRef.current = renderCitation;
  const components = useMemo<Components>(
    () => ({
      pre: CodeBlock,
      a: ({ node: _node, href, ...props }) => {
        const cite = href?.match(/^#cite-(\d+)$/);
        if (cite && renderRef.current) return renderRef.current(Number(cite[1]));
        return <a href={href} target="_blank" rel="noreferrer" {...props} />;
      },
    }),
    []
  );

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[[rehypeHighlight, { detect: true }]]}
      components={components}
    >
      {children}
    </ReactMarkdown>
  );
}
