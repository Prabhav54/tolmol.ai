# 🛒 tolmol.ai | E-Commerce Intelligence Engine

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector-3ECF8E.svg?logo=supabase)](https://supabase.com/)
[![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4.svg?logo=google)](https://ai.google.dev/)
[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-000000.svg?logo=vercel)](https://vercel.com/)

> **tolmol.ai** is an end-to-end e-commerce search and catalog intelligence engine. An ETL pipeline scrapes, deduplicates and embeds product pages into Supabase (PostgreSQL + pgvector). A hybrid RAG router then answers natural-language queries: hard constraints run as exact SQL, descriptive intent runs as vector similarity, and the final answer is generated **only** from catalog rows, so prices and links are never hallucinated.

---

## ✨ Key Features

* 🧠 **Hybrid RAG query router** — every query is parsed into structured filters. Descriptive queries (*"breathable summer running wear"*) go to **pgvector** cosine search over an HNSW index. Constraint queries (*"shoes under ₹2000 with rating > 4.2"*, *"phones between 10k and 20k on Flipkart"*) go to a **parameterized SQL query builder**; any leftover descriptive words still rank the filtered rows by semantic similarity. 100% routing accuracy on the bundled golden set (`benchmark/golden_set.json`).
* 🛡️ **Deduplicating ETL** — each product URL is normalized (tracking params, `www.`/`m.` prefixes, Amazon slugs → ASIN) and fingerprinted with **SHA-256**. Known URLs are skipped *before* scraping, and `ON CONFLICT (url_hash) DO NOTHING` guarantees no duplicate row is ever written. A second content hash avoids re-embedding unchanged products; price changes are appended to `price_history`.
* 🔎 **Robust extraction** — schema.org **JSON-LD** first, then OpenGraph/product meta tags, then **Gemini structured output** as a fallback for pages with no markup.
* 🔒 **Closed-domain answers** — the LLM (Gemini 2.5 Flash, or LLaMA-3 via Hugging Face) only sees retrieved catalog rows and must quote their exact prices. Empty results short-circuit with a fixed message (no LLM call), and if the LLM is down the API returns the ranked catalog list instead.
* 📊 **Zero-touch SQL analytics** — *"average price of t-shirts by platform"*, *"how many products under 1000"* compile to safe `COUNT / AVG / MIN / MAX … GROUP BY` queries; the UI shows the table, a chart and the SQL that ran.
* ⏱️ **Measured latency** — `/benchmark` reports p50/p95/p99 vector-retrieval latency over the live catalog against a **< 300 ms p95** target, plus routing accuracy. Every `/query` response includes per-stage timings.
* ⚡ **One deploy** — FastAPI serves both the JSON API and the web UI as a single Vercel function, pinned to the Mumbai region next to Supabase.

---

## 🏗️ System Architecture

```text
            ┌──────────── Ingestion (admin) ────────────┐
 URL ──► normalize + SHA-256 ──► known? ─yes─► skip (0 writes)
                                   │no
                                   ▼
          httpx fetch ─► JSON-LD / meta tags / Gemini fallback
                                   ▼
          Gemini embedding (768-d) ─► Supabase: products + price_history (pgvector, HNSW)

            ┌──────────── Query (shopper / operator) ───┐
 question ─► query parser ─► router
                               ├─ SEMANTIC ─► embed query ─► HNSW cosine top-k
                               └─ SQL ──────► filters (+ semantic re-rank) or COUNT/AVG/GROUP BY
                                   ▼
                     closed-domain synthesis (Gemini / LLaMA-3) ─► answer + product cards + SQL + timings
```

```text
tolmol.ai/
├── api/                      # FastAPI application
│   ├── main.py               # App, error handlers, health, static web UI mount
│   ├── index.py              # Vercel entrypoint
│   ├── schemas.py            # Pydantic request/response models
│   ├── routes/               # /ingest, /query, /products, /benchmark, /admin
│   └── services/             # ingestion.py (ETL + dedup), search.py (hybrid RAG pipeline)
├── engines/                  # ML / AI layer
│   ├── query_parser.py       # NL → structured filters (price, rating, platform, sort, aggregates)
│   ├── router.py             # SEMANTIC vs SQL intent routing
│   ├── vector_engine.py      # pgvector HNSW cosine search
│   ├── sql_engine.py         # Parameterized SQL builder + analytics aggregates
│   ├── embeddings.py         # Gemini / Hugging Face embeddings
│   ├── llm.py                # Gemini / LLaMA-3 generation + structured output
│   └── synthesis.py          # Closed-domain answer synthesis
├── scraper/                  # dedup.py (URL normalize + SHA-256), parser.py (fetch + extract), models.py
├── db/                       # models.py (tables, HNSW index), session.py (engine, init, schema checks), schema.sql
├── benchmark/                # evaluator.py, run_benchmark.py, golden_set.json
├── scripts/                  # init_db.py (schema / legacy archive), seed_catalog.py (demo, file, synthetic)
├── web/                      # Web UI: search, add products, insights, benchmark
├── tests/                    # Offline pytest suite (parser, router, dedup, extraction)
├── vercel.json               # Vercel build + region config
└── docker-compose.yml        # Local pgvector database
```

---

## 🔌 API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/ingest` | Scrape one URL → dedup → embed → store (`refresh: true` re-scrapes) |
| `POST` | `/ingest/batch` | Up to 25 URLs, per-URL results |
| `POST` | `/ingest/products` | Bulk import already-structured products (feeds / exports) |
| `POST` | `/query` | Hybrid RAG answer + product cards + SQL + timings |
| `GET` | `/query/route?q=` | Explain routing and extracted filters without running the query |
| `GET` | `/products`, `/products/{id}`, `/products/stats` | Catalog browsing, price history, dashboard stats |
| `POST` | `/benchmark` | Routing accuracy + retrieval latency percentiles |
| `POST` | `/admin/setup` | Create schema / archive legacy tables / seed demo data (needs `X-Admin-Token`) |
| `GET` | `/health`, `/docs` | Health check, interactive API docs |

---

## ⚙️ Local Setup

```bash
conda create -n hybrid-rag python=3.12 -y && conda activate hybrid-rag
pip install -r requirements-dev.txt
cp .env.example .env          # fill in DATABASE_URL and GOOGLE_API_KEY

python -m scripts.init_db     # add --archive-legacy if you have pre-2.0 tables
python -m scripts.seed_catalog --dummyjson   # ~190 demo products
python run.py                 # http://127.0.0.1:8000  (UI)  ·  /docs (API)
```

No Supabase yet? `docker compose up -d` starts pgvector on `localhost:5433`, which matches the default `DATABASE_URL`.

**Load testing at scale:** `python -m scripts.seed_catalog --synthetic 5000` generates 5,000 products (uses ~50 batched embedding calls), then `python -m benchmark.run_benchmark --samples 200`.

**Tests:** `pytest -q` (offline; no database or API keys needed).

> **Supabase connection timeouts?** Some campus/office networks block outbound ports 5432 and 6543. The deployed app is unaffected; to set up the database from there, set `ADMIN_TOKEN` and call `POST /admin/setup`.

---

## 🚀 Deploying to Vercel

1. Import the GitHub repo in Vercel (framework preset: **Other**). `vercel.json` builds `api/index.py` with the Python runtime and pins the function to `bom1` (Mumbai) to sit next to a Supabase `ap-south-1` database.
2. Set environment variables: `DATABASE_URL` (Supabase **transaction pooler**, port 6543), `GOOGLE_API_KEY`, `AUTO_INIT_DB=false`, `ADMIN_TOKEN` (any long random string), optionally `HUGGINGFACE_API_TOKEN` and `LLM_PROVIDER`.
3. One-time setup from the deployed app:
   ```bash
   curl -X POST https://<your-app>.vercel.app/admin/setup \
        -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
        -d '{"archive_legacy": true, "seed_dummyjson": true}'
   ```

---

## 🛠️ Tech Stack

* **Backend:** FastAPI, Uvicorn, Pydantic
* **Database:** Supabase PostgreSQL, pgvector (HNSW), SQLAlchemy, psycopg2
* **AI:** Google Gemini (`gemini-embedding-001`, `gemini-2.5-flash`), LLaMA-3 via Hugging Face Inference
* **Ingestion:** HTTPX, BeautifulSoup4, hashlib (SHA-256)
* **Frontend:** HTML/CSS/JS served by FastAPI, Chart.js
* **Deployment:** Vercel

---

## 👨‍💻 Author
### Prabhav Khare

GitHub: [@Prabhav54](https://github.com/Prabhav54)
LinkedIn: [Prabhav Khare](https://www.linkedin.com/in/prabhav-khare)
