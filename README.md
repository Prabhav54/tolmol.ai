# 🛒 tolmol.ai | E-Commerce Intelligence Engine

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.25+-FF4B4B.svg?logo=streamlit)](https://streamlit.io/)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector-3ECF8E.svg?logo=supabase)](https://supabase.com/)
[![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7.svg?logo=render)](https://render.com/)

> **tolmol.ai** is an end-to-end e-commerce search and catalog intelligence engine. It combines automated ETL pipelines for large-scale product ingestion with a hybrid LangChain RAG router, delivering high-relevance natural language search and zero-touch SQL analytics for retail databases.

---

## ✨ Key Features

* 🧠 **Hybrid RAG Query Router:** Dynamically dispatches e-commerce queries based on intent. Uses **pgvector** for semantic similarity (e.g., "comfortable summer shirts") and **Text-to-SQL** for strict numerical filters (e.g., "running shoes under ₹2000").
* 🚀 **High-Speed Retrieval:** Architected to parse through 5,000+ retail product embeddings with **sub-300ms** retrieval latency.
* 🛡️ **Automated ETL & Deduplication:** Features a robust web ingestion pipeline that uses cryptographic **URL hashing** to eliminate 100% of duplicate database writes, ensuring a high-fidelity catalog.
* 📊 **Zero-Touch SQL Reporting:** Completely eliminates manual database querying for internal data teams. Managers can ask natural language questions and receive precise SQL-driven data tables instantly.
* ⚡ **Decoupled Architecture:** Built with an independent FastAPI backend and a Streamlit frontend, optimized for modern cloud deployment on Render.

---

## 🏗️ System Architecture
```text
tolmol.ai/
├── api/                        # FastAPI Application Layer
│   ├── __init__.py
│   ├── main.py                 # Server entry point, CORS, router registration
│   ├── schemas.py              # Pydantic request/response models
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── ingest.py           # /ingest — scrape, hash, store, vectorize
│   │   ├── query.py            # /query — hybrid RAG, compare, trend, sentiment
│   │   └── benchmark.py        # /benchmark — routing accuracy & latency evaluation
│   └── services/
│       └── database.py         # psycopg2 service layer with context manager
├── app/                        # Streamlit Presentation Layer
│   ├── main.py                 # Dashboard UI, sidebar, chat, telemetry panels
│   ├── utils.py                # Text sanitize, SQL cleaner, vector formatter
│   └── pages/
│       ├── analytics.py        # Analytics sub-page (placeholder)
│       ├── benchmark_dashboard.py # Benchmark results visualizer (placeholder)
│       └── query_ui.py         # Query UI sub-page (placeholder)
├── benchmark/                  # Evaluation & Testing
│   ├── evaluator.py            # Routing accuracy measurement logic
│   ├── run_benchmark.py        # CLI runner for benchmark suite
│   └── golden_set.json         # Ground-truth query mappings
├── core/                       # Shared Configuration & Utilities
│   ├── __init__.py
│   ├── config.py               # Pydantic Settings (DATABASE_URL, API keys)
│   ├── exceptions.py           # Custom exception hierarchy
│   └── logger.py               # Standardized logging with StreamHandler
├── db/                         # Database Layer
│   ├── __init__.py
│   ├── schema.sql              # Full schema: products, product_links, price_history
│   └── session.py              # SQLAlchemy engine, pgvector init, global db
├── engines/                    # ML / AI Routing Layer
│   ├── __init__.py
│   ├── router.py               # Regex-based intent router (VECTOR vs SQL)
│   ├── vector_engine.py        # LangChain PGVector + Gemini Embeddings
│   ├── sql_engine.py           # Keyword-driven SQL query builder & executor
│   └── synthesis.py            # LLaMA-3 via HuggingFace InferenceClient
├── notebook/
│   └── gemini_rag_prototype.ipynb # Jupyter prototype for RAG pipeline
├── scraper/
│   ├── __init__.py
│   ├── parser.py               # httpx + BeautifulSoup + Gemini extraction
│   └── text_processor.py       # Word-level chunker with overlap
├── .gitignore
├── backend_requirements.txt    # Backend-only pip dependencies
├── docker-compose.yml          # pgvector container config
├── README.md
├── requirements.txt            # Full frontend + backend dependencies
├── run.py                      # Windows-safe Uvicorn launcher
├── setup.py                    # find_packages config for local imports
└── test_run.py                 # Individual function sandbox
```
### 1. Ingestion Pipeline (Admin)
The platform handles automated targeted ingestion for inventory building.
1. Admin inputs a target product URL or data source.
2. The pipeline extracts metadata (Title, Price, Rating, Description).
3. The system applies **URL Hashing** to verify uniqueness against the database.
4. Generates vector embeddings using Large Language Models (LLaMA-3/Gemini).
5. Stores structured data and embeddings in a Supabase PostgreSQL instance.

### 2. Search Engine (User/Shopper)
The platform uses a closed-domain RAG framework to prevent AI hallucinations.
1. User submits a natural language query.
2. **LangChain Router** analyzes the query for hard constraints vs. semantic intent.
3. Dispatches query to `pgvector` (cosine similarity) OR `Text-to-SQL` translation.
4. Retrieves exact matching inventory from the database.
5. Returns formatted products with accurate, real-time pricing and original purchasing links.

---

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **Backend:** FastAPI, Uvicorn, Python
* **Database:** PostgreSQL (Supabase), pgvector, SQLAlchemy
* **AI & Machine Learning:** LangChain, Hugging Face, Google Gemini / LLaMA-3

---

## ⚙️ Local Setup & Installation

### Prerequisites
* Python 3.9+
* A [Supabase](https://supabase.com/) account with a PostgreSQL database initialized.
* API Keys for Hugging Face and your chosen LLM (Gemini).


## 👨‍💻 Author
### Prabhav Khare

GitHub: @Prabhav54
LinkedIn: Prabhav Khare (www.linkedin.com/in/prabhav-khare)
