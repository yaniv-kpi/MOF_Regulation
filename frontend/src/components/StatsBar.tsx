"use client";

import { useEffect, useState } from "react";
import { Database, Clock } from "lucide-react";
import { getStats } from "@/lib/api";
import type { StatsResponse } from "@/lib/types";

export default function StatsBar() {
  const [stats, setStats] = useState<StatsResponse | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => {});
  }, []);

  if (!stats) return null;

  return (
    <div
      className="flex flex-wrap items-center justify-center gap-4 text-sm text-slate-500 dark:text-slate-400"
      dir="rtl"
    >
      <span className="flex items-center gap-1.5">
        <Database className="w-3.5 h-3.5" />
        <span className="font-medium text-slate-700 dark:text-slate-300">
          {stats.total_documents.toLocaleString("he-IL")}
        </span>
        <span>מסמכים במאגר</span>
      </span>
      {stats.last_crawled && (
        <span className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          <span>עודכן לאחרונה: {new Date(stats.last_crawled).toLocaleDateString("he-IL")}</span>
        </span>
      )}
    </div>
  );
}
