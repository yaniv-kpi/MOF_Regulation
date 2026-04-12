"use client";

import { useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import SearchBar from "@/components/SearchBar";
import ResultCard from "@/components/ResultCard";
import LoadingState from "@/components/LoadingState";
import EmptyState from "@/components/EmptyState";
import StatsBar from "@/components/StatsBar";
import CategoryFilter from "@/components/CategoryFilter";
import { useSearch } from "@/hooks/useSearch";
import { ChevronRight, ChevronLeft, Zap } from "lucide-react";

function SearchPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const {
    query,
    setQuery,
    results,
    loading,
    error,
    page,
    category,
    setCategory,
    search,
    nextPage,
    prevPage,
  } = useSearch();

  // Sync URL params → state on load
  useEffect(() => {
    const q = searchParams.get("q") || "";
    const cat = searchParams.get("category") || "";
    const pg = parseInt(searchParams.get("page") || "1", 10);
    if (q) {
      setQuery(q);
      setCategory(cat);
      search(q, pg, cat);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = useCallback(
    (q: string) => {
      setQuery(q);
      search(q, 1, category);
      const params = new URLSearchParams({ q });
      if (category) params.set("category", category);
      router.push(`/?${params.toString()}`, { scroll: false });
    },
    [search, setQuery, category, router]
  );

  const handleCategoryChange = useCallback(
    (cat: string) => {
      setCategory(cat);
      if (query) {
        search(query, 1, cat);
        const params = new URLSearchParams({ q: query });
        if (cat) params.set("category", cat);
        router.push(`/?${params.toString()}`, { scroll: false });
      }
    },
    [query, search, setCategory, router]
  );

  const hasResults = results && results.results.length > 0;
  const isEmpty = results && results.results.length === 0 && !loading;
  const showHero = !results && !loading;

  return (
    <div className="relative">
      {/* Background decoration */}
      <div className="fixed inset-0 hero-gradient pointer-events-none" />
      <div className="fixed inset-0 dot-pattern pointer-events-none" />

      <div className="relative max-w-3xl mx-auto px-4 sm:px-6">

        {/* ── Hero section ── */}
        {showHero && (
          <div className="flex flex-col items-center text-center pt-20 pb-12 gap-6 animate-fade-in" dir="rtl">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-50 dark:bg-brand-900/30 border border-brand-100 dark:border-brand-800 text-brand-700 dark:text-brand-300 text-sm font-medium">
              <Zap className="w-3.5 h-3.5" />
              <span>חיפוש מלא-טקסט בעברית</span>
            </div>

            {/* Headline */}
            <div>
              <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight leading-tight">
                חפש ב
                <span className="text-brand-600 dark:text-brand-400"> תקנות ישראל</span>
              </h1>
              <p className="mt-3 text-lg text-slate-500 dark:text-slate-400 max-w-lg mx-auto">
                גישה מיידית לאלפי מסמכי תקנות, חוקים ונהלים מתוך מאגר gov.il
              </p>
            </div>

            {/* Search bar */}
            <div className="w-full max-w-2xl">
              <SearchBar
                value={query}
                onChange={setQuery}
                onSearch={handleSearch}
                loading={loading}
                size="hero"
              />
            </div>

            {/* Stats */}
            <StatsBar />

            {/* Sample queries */}
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              {["הגנת הצרכן", "חוק עבודה", "רישוי עסקים", "ביטוח לאומי", "תכנון ובנייה"].map((q) => (
                <button
                  key={q}
                  onClick={() => handleSearch(q)}
                  className="px-3 py-1.5 text-sm rounded-full border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-400 transition-all bg-white/70 dark:bg-slate-800/50 backdrop-blur-sm"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Results header ── */}
        {(hasResults || loading || error) && (
          <div className="pt-6 pb-4" dir="rtl">
            {/* Compact search bar */}
            <div className="mb-5">
              <SearchBar
                value={query}
                onChange={setQuery}
                onSearch={handleSearch}
                loading={loading}
                size="compact"
              />
            </div>

            {/* Category filter */}
            {!loading && hasResults && (
              <div className="mb-4">
                <CategoryFilter selected={category} onChange={handleCategoryChange} />
              </div>
            )}

            {/* Result count + timing */}
            {results && !loading && (
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="text-slate-500 dark:text-slate-400">
                  נמצאו{" "}
                  <span className="font-semibold text-slate-800 dark:text-white">
                    {results.total.toLocaleString("he-IL")}
                  </span>{" "}
                  תוצאות
                </span>
                <span className="text-slate-400 dark:text-slate-500 text-xs">
                  זמן חיפוש: {results.search_time_ms}ms
                </span>
              </div>
            )}
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-4 text-sm text-red-700 dark:text-red-400 mb-4" dir="rtl">
            {error}
          </div>
        )}

        {/* ── Loading skeletons ── */}
        {loading && <LoadingState />}

        {/* ── Empty state ── */}
        {isEmpty && <EmptyState query={query} />}

        {/* ── Results list ── */}
        {hasResults && !loading && (
          <div className="flex flex-col gap-3 pb-8">
            {results.results.map((doc, i) => (
              <ResultCard key={doc.id} doc={doc} query={query} index={i} />
            ))}

            {/* Pagination */}
            {(page > 1 || results.has_more) && (
              <div className="flex items-center justify-center gap-3 pt-4" dir="rtl">
                <button
                  onClick={prevPage}
                  disabled={page <= 1}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                  <span>הקודם</span>
                </button>

                <span className="text-sm text-slate-500 dark:text-slate-400 px-2">
                  עמוד {page}
                </span>

                <button
                  onClick={nextPage}
                  disabled={!results.has_more}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                >
                  <span>הבא</span>
                  <ChevronLeft className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <SearchPage />
    </Suspense>
  );
}
