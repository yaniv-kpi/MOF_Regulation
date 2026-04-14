"use client";

import { useState } from "react";
import { RefreshCw, Database, ExternalLink } from "lucide-react";
import { triggerCrawl } from "@/lib/api";

interface CrawlBannerProps {
  onCrawlStarted: () => void;
}

export default function CrawlBanner({ onCrawlStarted }: CrawlBannerProps) {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleCrawl = async () => {
    setLoading(true);
    try {
      await triggerCrawl();
      setDone(true);
      onCrawlStarted();
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/30 px-4 py-3 text-sm text-green-700 dark:text-green-400 flex items-center gap-2" dir="rtl">
        <RefreshCw className="w-4 h-4 animate-spin flex-shrink-0" />
        <span>
          הסריקה החלה ברקע — המסמכים יופיעו תוך מספר דקות. ניתן לחפש כבר עכשיו.
        </span>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-4 flex flex-col sm:flex-row items-start sm:items-center gap-3"
      dir="rtl"
    >
      <Database className="w-5 h-5 text-amber-500 dark:text-amber-400 flex-shrink-0 mt-0.5 sm:mt-0" />
      <div className="flex-1 text-sm text-amber-800 dark:text-amber-300">
        <span className="font-semibold">מאגר המסמכים ריק.</span>{" "}
        לחץ על הכפתור כדי לטעון את כל קבצי ה-PDF ו-Word מ{" "}
        <a
          href="https://www.gov.il/he/pages/information-entities-codex"
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2 hover:text-amber-600 dark:hover:text-amber-200 inline-flex items-center gap-0.5"
        >
          gov.il
          <ExternalLink className="w-3 h-3" />
        </a>
        .
      </div>
      <button
        onClick={handleCrawl}
        disabled={loading}
        className="flex-shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white transition-colors"
      >
        <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        <span>{loading ? "מתחיל…" : "טען מסמכים"}</span>
      </button>
    </div>
  );
}
