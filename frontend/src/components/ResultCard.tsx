"use client";

import { ExternalLink, Tag, Calendar, FileText } from "lucide-react";
import type { DocumentResult } from "@/lib/types";
import clsx from "clsx";

interface ResultCardProps {
  doc: DocumentResult;
  query: string;
  index: number;
}

/** Wrap occurrences of `keyword` in <mark> tags for display. */
function highlightText(text: string, query: string): string {
  if (!query.trim()) return text;
  const words = query.trim().split(/\s+/).filter(Boolean);
  let result = text;
  for (const word of words) {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escaped})`, "gi");
    result = result.replace(regex, '<mark class="highlight">$1</mark>');
  }
  return result;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  regulation: "תקנות",
  law: "חוק",
  pdf: "מסמך PDF",
  order: "צו",
  procedure: "נוהל",
};

export default function ResultCard({ doc, query, index }: ResultCardProps) {
  // The snippet may already contain <mark> tags from PostgreSQL ts_headline.
  // If not, we apply client-side highlighting.
  const hasServerHighlight = doc.snippet.includes("<mark");
  const snippetHtml = hasServerHighlight
    ? doc.snippet
    : highlightText(doc.snippet, query);

  const titleHtml = highlightText(doc.title, query);
  const typeLabel = DOC_TYPE_LABELS[doc.document_type] || doc.document_type || "מסמך";

  return (
    <article
      className={clsx(
        "group relative flex flex-col gap-3 rounded-2xl border bg-white dark:bg-slate-800/60",
        "border-slate-200 dark:border-slate-700/60",
        "p-5 sm:p-6 transition-all duration-200",
        "hover:border-brand-300 dark:hover:border-brand-600",
        "hover:shadow-md dark:hover:shadow-brand-900/20",
        "animate-slide-up"
      )}
      style={{ animationDelay: `${index * 60}ms` }}
      dir="rtl"
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Badges */}
          <div className="flex flex-wrap items-center gap-1.5 mb-2">
            {doc.category && (
              <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300 border border-brand-100 dark:border-brand-800">
                <Tag className="w-3 h-3" />
                {doc.category}
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
              <FileText className="w-3 h-3" />
              {typeLabel}
            </span>
            {doc.published_date && (
              <span className="inline-flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                <Calendar className="w-3 h-3" />
                {doc.published_date}
              </span>
            )}
          </div>

          {/* Title */}
          <h2
            className="text-base sm:text-lg font-semibold text-slate-900 dark:text-white leading-snug group-hover:text-brand-700 dark:group-hover:text-brand-400 transition-colors"
            dangerouslySetInnerHTML={{ __html: titleHtml }}
          />
        </div>
      </div>

      {/* Snippet */}
      <p
        className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-3 text-right"
        dangerouslySetInnerHTML={{ __html: snippetHtml }}
      />

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-700/50 mt-auto">
        <span className="text-xs text-slate-400 dark:text-slate-500 truncate max-w-[200px] ltr:text-left rtl:text-right" dir="ltr">
          {doc.url}
        </span>

        <a
          href={doc.url}
          target="_blank"
          rel="noopener noreferrer"
          className={clsx(
            "inline-flex items-center gap-1.5 text-sm font-medium rounded-lg px-3 py-1.5",
            "bg-brand-600 hover:bg-brand-700 text-white",
            "transition-all duration-150 shadow-sm hover:shadow",
            "flex-shrink-0"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <span>פתח מסמך</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </article>
  );
}
