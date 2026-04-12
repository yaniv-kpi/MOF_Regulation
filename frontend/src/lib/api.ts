import axios from "axios";
import type { SearchParams, SearchResponse, StatsResponse } from "./types";

/**
 * Resolve backend base URL at runtime so the same build works in both:
 *  - Local dev  (localhost) → http://localhost:8000
 *  - Deployed via experimentalServices → /_/backend  (same-origin, no port needed)
 *
 * Priority: NEXT_PUBLIC_API_URL env var → runtime hostname detection
 */
function resolveBaseURL(): string {
  // Explicit override (set NEXT_PUBLIC_API_URL in .env.local for local dev if needed)
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;

  // Client-side runtime detection
  if (typeof window !== "undefined") {
    const { hostname } = window.location;
    const isLocal = hostname === "localhost" || hostname === "127.0.0.1";
    return isLocal ? "http://localhost:8000" : "/_/backend";
  }

  // SSR fallback (shouldn't be reached — all calls are "use client")
  return "http://localhost:8000";
}

const api = axios.create({
  baseURL: resolveBaseURL(),
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

export async function searchDocuments(
  params: SearchParams
): Promise<SearchResponse> {
  const { data } = await api.get<SearchResponse>("/api/search", { params });
  return data;
}

export async function getSuggestions(q: string): Promise<string[]> {
  if (!q || q.length < 2) return [];
  try {
    const { data } = await api.get<{ suggestions: string[] }>("/api/suggest", {
      params: { q },
    });
    return data.suggestions;
  } catch {
    return [];
  }
}

export async function getStats(): Promise<StatsResponse> {
  const { data } = await api.get<StatsResponse>("/api/stats");
  return data;
}

export async function getCategories(): Promise<string[]> {
  const { data } = await api.get<{ categories: string[] }>("/api/categories");
  return data.categories;
}

export async function triggerCrawl(): Promise<void> {
  await api.post("/api/crawl");
}
