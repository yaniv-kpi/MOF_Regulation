import axios from "axios";
import type { SearchParams, SearchResponse, StatsResponse } from "./types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
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
