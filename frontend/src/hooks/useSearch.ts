"use client";

import { useState, useCallback, useRef } from "react";
import { searchDocuments, getSuggestions } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

export function useSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<string>("");

  const abortRef = useRef<AbortController | null>(null);

  const search = useCallback(
    async (q: string, pg = 1, cat = category) => {
      if (!q.trim()) return;

      // Cancel previous in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setLoading(true);
      setError(null);

      try {
        const data = await searchDocuments({
          q: q.trim(),
          page: pg,
          limit: 10,
          category: cat || undefined,
        });
        setResults(data);
        setPage(pg);
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "CanceledError") return;
        setError("חיפוש נכשל. אנא נסה שוב.");
      } finally {
        setLoading(false);
      }
    },
    [category]
  );

  const nextPage = useCallback(() => {
    if (results?.has_more) {
      search(query, page + 1);
    }
  }, [results, query, page, search]);

  const prevPage = useCallback(() => {
    if (page > 1) {
      search(query, page - 1);
    }
  }, [query, page, search]);

  const reset = useCallback(() => {
    setQuery("");
    setResults(null);
    setError(null);
    setPage(1);
    setCategory("");
  }, []);

  return {
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
    reset,
  };
}

export function useAutocomplete() {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSuggestions = useCallback((q: string) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!q || q.length < 2) {
      setSuggestions([]);
      return;
    }
    timerRef.current = setTimeout(async () => {
      const s = await getSuggestions(q);
      setSuggestions(s);
    }, 300);
  }, []);

  const clearSuggestions = useCallback(() => setSuggestions([]), []);

  return { suggestions, fetchSuggestions, clearSuggestions };
}
