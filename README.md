# 🛒 tolmol.ai | Price Comparison for Indian Stores

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector-3ECF8E.svg?logo=supabase)](https://supabase.com/)
[![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4.svg?logo=google)](https://ai.google.dev/)
[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-000000.svg?logo=vercel)](https://vercel.com/)

> **tolmol.ai** compares a product's price across Indian stores. Paste a link from Amazon, Flipkart, Croma or any other store, type what you want (in English or Hinglish), or upload a photo. tolmol.ai finds the same model on other stores, records a daily price history, gives a buy-or-wait verdict and answers questions about the product's price, specs and reviews from facts it has stored.

---

## ✨ Key Features

* 🔗 **Paste any product link.** The page is scraped first (schema.org JSON-LD, then meta tags) for a live price. A store that blocks scrapers is looked up through Gemini with Google Search grounding instead.
* 🗣️ **Search by name or photo.** Messy or Hinglish queries (*"joote 2000 ke andar"*) become a list of real products sold in India. A photo goes to Gemini vision, which names the product and up to two close alternatives.
* 🏪 **Strict cross-store matching.** Each listing is checked by model number, edition words (*Pro / Ultra / Lite*), storage variant and title similarity. Listings priced far from the rest are dropped, and every product link is opened to confirm it works. When a page can't be confirmed, you get a link to the store's search page instead of a guessed product URL.
* 📈 **Price history and verdict.** Each comparison is saved as a price snapshot. A daily Vercel Cron re-checks tracked products, so the chart, lowest/average/highest prices and the *Great time to buy / Consider waiting* verdict improve over time.
* 💬 **Chat with the product.** Each question is routed by English and Hinglish keyword rules, with an LLM fallback. **PRICE** questions run SQL over listings and snapshots. **SPECS** combine a JSONB spec lookup with hybrid search. **REVIEWS** and **GENERAL** use hybrid retrieval: pgvector cosine plus Postgres full-text search, fused with reciprocal rank fusion, then reranked by the LLM. Answers come only from the retrieved facts.
* 🔔 **Price-drop alerts** by email through Resend, sent by the daily refresh.
* 🔑 **API keys and rate limits.** Anonymous callers get an hourly allowance, and API keys get a daily one. Operator endpoints report search volume, failed lookups and which store is cheapest most often.
* 🧯 **Graceful degradation.** Without a database, comparisons still work (no history or chat). Without an AI key, a pasted link still shows the store you pasted.

---

## 🏗️ Architecture

```text
 link / query / photo
        │
        ▼
 identity.py ── scrape page (JSON-LD/meta) ─┐
             └─ Gemini + Google Search ─────┴─► canonical product (brand · model · variant)
        │
        ▼
 market.py ── Gemini grounded search per store ─► match_score + price outliers ─► verify links
        │
        ▼
 tracker.py ── Postgres: tracked_products · listings · price_snapshots ─► analysis.py (chart + verdict)
        │                                                               └► alerts.py (Resend)
        ▼
 chat.py ── chat_router (rules → LLM) ─┬─ PRICE  → SQL
                                       ├─ SPECS  → JSONB SQL + hybrid search
                                       └─ REVIEWS/GENERAL → pgvector + full-text, RRF, LLM rerank
```

```text
tolmol.ai/
├── api/index.py              # Vercel entrypoint (exports tolmol.main:app)
├── tolmol/
│   ├── main.py               # FastAPI app, error handlers, /api/health, local static mount of public/
│   ├── config.py             # Settings from env / .env
│   ├── schemas.py            # Request models + ProductIdentity (identity key)
│   ├── routes/               # shopper.py (/api/compare, /search, /products/...), operator.py (/api/admin, /api/cron)
│   ├── services/             # identity, market, matching, compare, tracker, analysis, insights,
│   │                         # retrieval, chat, chat_router, alerts, access
│   ├── scraping/             # extract.py (fetch + JSON-LD/meta), platforms.py (store registry), urls.py
│   ├── ai/                   # llm.py (Gemini / LLaMA-3, grounded search, structured output), embeddings.py
│   └── db/                   # models.py (tables, HNSW + GIN indexes), session.py (engine, init_db)
├── public/                   # Web UI (index.html, app.js, styles.css), served by the Vercel CDN
├── scripts/init_db.py        # Create tables and indexes
├── tests/                    # Offline pytest suite
├── run.py                    # Local dev server
├── vercel.json               # Function, /api rewrite, daily cron, Mumbai region
└── docker-compose.yml        # Local pgvector database
```

---

## 🔌 API

Interactive docs: `/api/docs`. Send `X-API-Key` for higher limits.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/compare` | `{"url": ...}` or `{"product": {...}}` → prices across stores, history, verdict (`refresh: true` skips the 6 h cache) |
| `POST` | `/api/search` | Free-text / Hinglish search → products to pick from |
| `POST` | `/api/search/photo` | Base64 image → products to pick from |
| `GET` | `/api/products/recent` | Recently compared products |
| `GET` | `/api/products/{id}` | Saved comparison, history and insights |
| `POST` | `/api/products/{id}/insights` | Research specs + reviews and index them for chat |
| `POST` | `/api/products/{id}/chat` | Ask about price, specs or reviews |
| `POST` | `/api/products/{id}/alerts` | Email alert at a target price |
| `POST` | `/api/admin/setup` | Create tables and indexes (`X-Admin-Token`) |
| `GET` | `/api/admin/insights` | Usage, failed lookups, cheapest-store stats (`X-Admin-Token`) |
| `GET/POST/DELETE` | `/api/admin/api-keys` | Manage API keys (`X-Admin-Token`) |
| `GET` | `/api/cron/refresh` | Daily re-check + alerts (`Authorization: Bearer $CRON_SECRET`) |
| `GET` | `/api/health` | Database and search status |

---

## ⚙️ Local Setup

```bash
conda create -n tolmol python=3.12 -y && conda activate tolmol
pip install -r requirements-dev.txt
cp .env.example .env          # fill in DATABASE_URL and GOOGLE_API_KEY

python -m scripts.init_db     # create tables (also runs on startup when AUTO_INIT_DB=true)
python run.py                 # http://127.0.0.1:8000  (UI)  ·  /api/docs (API)
```

No Supabase yet? `docker compose up -d` starts pgvector on `localhost:5433`, which matches the default `DATABASE_URL`.

**Tests:** `pytest -q` (offline; no database or API keys needed).

> **Supabase connection timeouts?** Some campus/office networks block outbound ports 5432 and 6543. The deployed app is unaffected; to set up the database from there, set `ADMIN_TOKEN` and call `POST /api/admin/setup`.

---

## 🚀 Deploying to Vercel

1. Import the GitHub repo in Vercel (framework preset: **Other**). `public/` is served by the CDN; `/api/*` is rewritten to the Python function `api/index.py`, pinned to `bom1` (Mumbai) next to a Supabase `ap-south-1` database.
2. Set environment variables: `DATABASE_URL` (Supabase **transaction pooler**, port 6543), `GOOGLE_API_KEY`, `AUTO_INIT_DB=false`, `ADMIN_TOKEN`, `CRON_SECRET`, `PUBLIC_BASE_URL`, and optionally `RESEND_API_KEY`, `HUGGINGFACE_API_TOKEN`, `LLM_PROVIDER`.
3. One-time setup from the deployed app:
   ```bash
   curl -X POST https://<your-app>.vercel.app/api/admin/setup -H "X-Admin-Token: $ADMIN_TOKEN"
   ```
4. The cron in `vercel.json` calls `/api/cron/refresh` daily at 07:00 IST and re-checks the `CRON_BATCH` least recently compared products.

---

## 🛠️ Tech Stack

* **Backend:** FastAPI, Uvicorn, Pydantic
* **Database:** Supabase PostgreSQL, pgvector (HNSW), Postgres full-text search (GIN), SQLAlchemy, psycopg2
* **AI:** Google Gemini (`gemini-2.5-flash` with Google Search grounding and vision, `gemini-embedding-001`), LLaMA-3 via Hugging Face Inference
* **Scraping:** HTTPX, BeautifulSoup4
* **Frontend:** Plain HTML/CSS/JS, Chart.js
* **Email:** Resend
* **Deployment:** Vercel (Python function + CDN + Cron)

---

## 👨‍💻 Author
### Prabhav Khare

GitHub: [@Prabhav54](https://github.com/Prabhav54)
LinkedIn: [Prabhav Khare](https://www.linkedin.com/in/prabhav-khare)
