# 🛍️ Hybrid RAG E-Commerce Intelligence Platform

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a67d.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.25+-FF4B4B.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Sentence--Transformers-F9AB00.svg)

A production-grade Retrieval-Augmented Generation (RAG) pipeline designed for dynamic e-commerce analytics. This platform bypasses aggressive anti-bot mechanisms to scrape real-time product data (including pricing and variants) from platforms like Flipkart and Amazon, processes the text into dense vector embeddings, and allows users to query the context using natural language.

## 🚀 Key Features

* **Cloud-Rendered Ingestion:** Utilizes Jina AI's Reader API to bypass local OS async loop limitations and anti-bot captchas, seamlessly rendering JavaScript to capture dynamic pricing.
* **Automated ID Hashing:** Silently hashes product URLs into unique 6-digit integers via `hashlib` to prevent database duplication and streamline the user experience.
* **High-Performance Vector Engine:** Embeds text chunks locally using Hugging Face `SentenceTransformers` and stores them in PostgreSQL using the `pgvector` extension for sub-millisecond similarity search.
* **Asynchronous Backend API:** Built on FastAPI for high-throughput, non-blocking request handling.
* **Interactive Analytics Dashboard:** A sleek, conversational Streamlit UI featuring persistent chat history and real-time backend metric tracking.

---

## 🏗️ Project Architecture & File Structure

```text
hybrid-rag-ecommerce/
│
├── api/
│   ├── main.py                 # FastAPI application entry point, CORS config, and route inclusion
│   └── routes/
│       ├── ingest.py           # API endpoint for triggering product scraping and database insertion
│       └── query.py            # API endpoint for routing natural language questions to the LLM
│
├── app/
│   └── main.py                 # Streamlit frontend dashboard (UI, chat state, URL hashing)
│
├── core/
│   ├── config.py               # Pydantic BaseSettings for env vars (DB credentials, chunk sizes)
│   └── logger.py               # Centralized logging configuration for debugging the pipeline
│
├── db/
│   └── session.py              # PostgreSQL SQLAlchemy engine initialization and connection pool
│
├── engines/
│   └── vector_engine.py        # ML data layer: Handles text-to-vector encoding and pgvector SQL ops
│
├── scraper/
│   └── parser.py               # Extraction layer: Interfaces with Jina Cloud to pull and chunk raw HTML
│
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
