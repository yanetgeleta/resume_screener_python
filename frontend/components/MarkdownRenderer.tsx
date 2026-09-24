"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

function normalizeContent(raw: string): string {
  if (!raw) return "";
  // Unescape any XML/HTML entities like &lt;br&gt; and normalize [br] tags
  return raw
    .replace(/&lt;br\s*\/?&gt;/gi, "<br />")
    .replace(/\[br\]/gi, "<br />");
}

export default function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  const processedContent = normalizeContent(content);

  return (
    <div className={`prose-dark max-w-none text-sm leading-relaxed ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto my-3 rounded-xl border border-zinc-700/80 bg-zinc-900/90 shadow-xl shadow-black/20">
              <table className="min-w-full divide-y divide-zinc-700/80 text-left text-xs" {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => (
            <thead className="bg-zinc-800/90 text-zinc-200 font-semibold uppercase tracking-wider text-[11px]" {...props} />
          ),
          tbody: ({ node, ...props }) => (
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300" {...props} />
          ),
          tr: ({ node, ...props }) => (
            <tr className="hover:bg-zinc-800/40 transition-colors even:bg-zinc-800/20 odd:bg-transparent" {...props} />
          ),
          th: ({ node, ...props }) => (
            <th className="px-4 py-3 font-semibold text-zinc-100 border-b border-zinc-700/80 select-none whitespace-nowrap" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="px-4 py-2.5 text-xs text-zinc-300 align-top leading-relaxed border-b border-zinc-800/40 whitespace-pre-line" {...props} />
          ),
          br: ({ node, ...props }) => (
            <br className="my-1" {...props} />
          ),
          h1: ({ node, ...props }) => (
            <h1 className="text-base font-bold text-zinc-100 mt-4 mb-2 tracking-tight flex items-center gap-1.5" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="text-sm font-bold text-zinc-100 mt-3 mb-1.5 tracking-tight flex items-center gap-1.5" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="text-xs font-semibold text-zinc-200 mt-2 mb-1" {...props} />
          ),
          p: ({ node, ...props }) => (
            <p className="mb-2 last:mb-0 leading-relaxed text-zinc-200" {...props} />
          ),
          ul: ({ node, ...props }) => (
            <ul className="list-disc list-outside pl-5 mb-2.5 space-y-1 text-zinc-300" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="list-decimal list-outside pl-5 mb-2.5 space-y-1 text-zinc-300" {...props} />
          ),
          li: ({ node, ...props }) => (
            <li className="leading-relaxed" {...props} />
          ),
          strong: ({ node, ...props }) => (
            <strong className="font-semibold text-white" {...props} />
          ),
          em: ({ node, ...props }) => (
            <em className="italic text-zinc-300" {...props} />
          ),
          code: ({ node, className, children, ...props }: any) => {
            const isInline = !className && typeof children === "string" && !children.includes("\n");
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 rounded-md bg-zinc-800/90 border border-zinc-700/60 font-mono text-[11px] text-blue-300" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <pre className="p-3.5 my-2.5 rounded-xl bg-zinc-950 border border-zinc-800 overflow-x-auto text-xs font-mono text-zinc-300 shadow-inner">
                <code {...props}>{children}</code>
              </pre>
            );
          },
          blockquote: ({ node, ...props }) => (
            <blockquote className="border-l-2 border-blue-500 pl-3.5 my-2 italic text-zinc-400 bg-blue-500/5 py-1.5 rounded-r-lg" {...props} />
          ),
          hr: ({ node, ...props }) => (
            <hr className="my-3 border-zinc-800" {...props} />
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}
