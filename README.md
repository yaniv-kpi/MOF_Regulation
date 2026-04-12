# חיפוש תקנות ישראל — Israeli Regulation Search Engine

Full-text search engine for Israeli regulation documents from [gov.il](https://www.gov.il/he/pages/information-entities-codex).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Next.js Frontend                       │
│  (RTL Hebrew UI · TailwindCSS · Autocomplete · Dark mode)  │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API
┌───────────────────────────▼─────────────────────────────────┐
│                     FastAPI Backend                         │
│  /api/search  /api/suggest  /api/stats  /api/crawl         │
└───────────────────────────┬─────────────────────────────────┘
                            │ SQLAlchemy
┌───────────────────────────▼─────────────────────────────────┐
│                     PostgreSQL 16                           │
│  tsvector FTS (simple config) · GIN index · pg_trgm        │
└─────────────────────────────────────────────────────────────┘
                            ▲
                  Background crawler
                  (gov.il scraper)
```

## Quick Start (Docker Compose — recommended)

```bash
# 1. Clone and enter the project
cd israeli-reg-search

# 2. Copy env files
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# 3. Start all services
docker compose up --build

# 4. Load sample data (in a new terminal)
docker compose exec backend python -m app.seed

# 5. Open the app
open http://localhost:3000
```

## Manual Setup (without Docker)

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment
cp .env.example .env
# Edit .env — set DATABASE_URL to your Postgres instance

# Start server
uvicorn app.main:app --reload --port 8000
```

### Load sample data

```bash
# Activate venv first
python -m app.seed
```

### Run the web crawler (fetches real gov.il documents)

```bash
# POST to the crawl endpoint (runs in background)
curl -X POST http://localhost:8000/api/crawl
```

### Frontend

```bash
cd frontend
npm install

cp .env.local.example .env.local
# Edit .env.local if backend runs on a different URL

npm run dev
# → http://localhost:3000
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search?q=תקנות&page=1&limit=10&category=` | Full-text search |
| GET | `/api/suggest?q=הגנת` | Autocomplete suggestions |
| GET | `/api/categories` | List all categories |
| GET | `/api/stats` | Document count & last crawl |
| POST | `/api/crawl` | Trigger background crawl |
| GET | `/health` | Healthcheck |

### Search response example

```json
{
  "query": "הגנת הצרכן",
  "total": 42,
  "page": 1,
  "limit": 10,
  "has_more": true,
  "results": [
    {
      "id": 1,
      "title": "חוק הגנת הצרכן, התשמ\"א-1981",
      "url": "https://www.gov.il/...",
      "snippet": "...חוק <mark>הגנת הצרכן</mark> מגן על הזכות...",
      "category": "הגנת הצרכן",
      "document_type": "law",
      "published_date": "1981",
      "rank": 0.859
    }
  ],
  "search_time_ms": 12.4
}
```

## Search Engine Details

- **FTS Engine**: PostgreSQL `tsvector` with `simple` configuration
  - `simple` config tokenizes on whitespace, lowercases, handles Unicode properly — works for Hebrew
  - Title weighted **A** (higher priority), content weighted **B**
- **Ranking**: `ts_rank_cd` with normalization
- **Fallback chain**: FTS (AND) → FTS (OR) → ILIKE (substring)
- **Fuzzy autocomplete**: `pg_trgm` trigram similarity on title column
- **Snippets**: `ts_headline` generates highlighted excerpts server-side
- **Index**: GIN on `search_vector`, GIN trigram on `title`

## Crawler Strategy

The crawler targets `https://www.gov.il/he/pages/information-entities-codex`:

1. **API-first**: tries gov.il's JSON API endpoints
2. **HTML fallback**: parses the page with BeautifulSoup, follows document links
3. **PDF support**: downloads PDF files and extracts text with `pypdf`
4. **Politeness**: 1-second delay between requests
5. **Upsert**: re-crawling updates existing documents, doesn't duplicate

## Project Structure

```
israeli-reg-search/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + endpoints
│   │   ├── config.py        # Pydantic settings
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   ├── models.py        # Document ORM model
│   │   ├── schemas.py       # Pydantic request/response models
│   │   ├── search.py        # Search service (FTS + fallbacks)
│   │   ├── seed.py          # Sample data loader
│   │   └── crawler/
│   │       ├── govil_crawler.py   # gov.il web crawler
│   │       └── text_extractor.py  # HTML/PDF text extraction
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx   # Root layout (RTL, dark mode, fonts)
│   │   │   ├── page.tsx     # Main search page
│   │   │   └── globals.css  # Tailwind + highlight styles
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── SearchBar.tsx      # Autocomplete search input
│   │   │   ├── ResultCard.tsx     # Document result card
│   │   │   ├── LoadingState.tsx   # Skeleton loaders
│   │   │   ├── EmptyState.tsx
│   │   │   ├── CategoryFilter.tsx # Category pills
│   │   │   └── StatsBar.tsx       # Document count display
│   │   ├── hooks/
│   │   │   └── useSearch.ts  # Search state + autocomplete hook
│   │   └── lib/
│   │       ├── api.ts        # Axios API client
│   │       └── types.ts      # TypeScript interfaces
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.mjs
└── docker-compose.yml
```

## Performance Notes

- GIN index on `search_vector`: sub-10ms for typical Hebrew FTS queries
- `ts_rank_cd` with `|32` normalization: favors shorter, more relevant docs
- `ts_headline` snippets are generated in one SQL query (no extra fetch)
- Pagination via `LIMIT/OFFSET` — switch to keyset pagination for >10k docs

## Dark Mode

Toggle with the moon/sun button in the header. Preference is saved in `localStorage`.

## Hebrew Text Support

All text is stored as UTF-8. The `simple` PostgreSQL FTS configuration:
- Does **not** stem words (correct for Hebrew — stemming tables don't exist)
- Lowercases Latin characters
- Tokenizes on whitespace and punctuation
- Handles RTL Unicode correctly

For semantic/AI-based search (bonus feature), replace the `search_vector` query with an embedding model query (e.g., `text-embedding-3-small` from OpenAI with `pgvector`).
