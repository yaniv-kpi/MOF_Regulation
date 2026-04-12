export interface DocumentResult {
  id: number;
  title: string;
  url: string;
  snippet: string;
  category: string;
  document_type: string;
  published_date: string;
  rank: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
  results: DocumentResult[];
  search_time_ms: number;
}

export interface StatsResponse {
  total_documents: number;
  categories: Array<{ category: string; cnt: number }>;
  last_crawled: string | null;
}

export interface SearchParams {
  q: string;
  page?: number;
  limit?: number;
  category?: string;
}
