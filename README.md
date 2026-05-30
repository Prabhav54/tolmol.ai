Markdown
# 🛍️ Hybrid RAG E-Commerce Intelligence Platform

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a67d.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.25+-FF4B4B.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Sentence--Transformers-F9AB00.svg)

A production-grade Retrieval-Augmented Generation (RAG) pipeline designed for dynamic e-commerce analytics. 

**How it works:** Users simply paste a product link from any e-commerce platform (like Amazon, Flipkart, or Wikipedia) into the interface. Once the product is ingested, users can ask natural language questions about the item. The backend bot intelligently routes the user's question to either a **Vector-Based Similarity Engine** (for qualitative questions like "What are the features?") or a **SQL-Based Analytics Engine** (for quantitative questions like "What is the exact price?"), ensuring highly accurate, context-aware answers.

## 🚀 Key Features

* **Intelligent Query Routing:** Automatically determines whether to use vector cosine similarity or structured SQL execution based on the user's prompt.
* **Cloud-Rendered Ingestion:** Utilizes Jina AI's Reader API to bypass local OS async loop limitations and anti-bot captchas, seamlessly rendering JavaScript to capture dynamic pricing.
* **Automated ID Hashing:** Silently hashes product URLs into unique 6-digit integers via `hashlib` to prevent database duplication.
* **High-Performance Vector Engine:** Embeds text chunks locally using Hugging Face `SentenceTransformers` and stores them in PostgreSQL using the `pgvector` extension for sub-millisecond similarity search.
* **Interactive Analytics Dashboard:** A sleek, conversational Streamlit UI featuring persistent chat history and real-time backend metric tracking.

---

## 🏗️ Project Architecture & Complete File Structure

```text
hybrid-rag-ecommerce/
│
├── .conda/                     # Local virtual environment configurations
├── .vscode/                    # VS Code workspace and debugging settings
│
├── api/                        # FastAPI Application Layer
│   ├── main.py                 # Server entry point and CORS configuration
│   └── routes/
│       ├── ingest.py           # Endpoint for triggering Cloud Jina scraping
│       └── query.py            # Endpoint for LLM routing and RAG generation
│
├── app/                        # Presentation Layer
│   └── main.py                 # Streamlit dashboard, UI layout, and chat state
│
├── benchmark/                  # Evaluation scripts for routing accuracy and latency
├── core/                       # Base configurations (Pydantic settings, logging)
├── db/                         # PostgreSQL SQLAlchemy engine and pooling
├── engines/                    # ML Layer: Vector embeddings and SQL execution logic
├── notebook/                   # Jupyter notebooks for isolated model experimentation
├── scraper/                    # Jina Reader API implementation and text chunking
│
├── .env                        # Secret environment variables (DB URLs, API Keys)
├── .gitignore                  # Prevents tracking of .env, __pycache__, and environments
├── docker-compose.yml          # Container orchestration for PostgreSQL and pgvector
├── README.md                   # Project documentation
├── requirements.txt            # Core Python dependencies
├── run.py                      # Explicit Windows-safe startup script for Uvicorn
├── setup.py                    # Package configuration for local module imports
└── test_run.py                 # Sandbox environment for testing individual functions
🛠️ Tech Stack
Data Science & ML: sentence-transformers, numpy

Backend Framework: FastAPI, uvicorn, pydantic

Frontend UI: Streamlit, requests

Database: PostgreSQL, pgvector, SQLAlchemy

Extraction: Jina Reader API (Cloud JS Rendering)

⚙️ Local Setup & Installation
1. Database Initialization
Ensure Docker is running, then spin up the database container:

Bash
docker-compose up -d
2. Environment Setup
Install the required dependencies:

Bash
pip install -r requirements.txt
3. Launching the Services
You will need two terminal windows to run the split architecture.

Terminal 1: Start the FastAPI Backend

Bash
set PYTHONPATH=. && python run.py
The backend will automatically verify your database schema and load the Hugging Face embedding models into memory.

Terminal 2: Start the Streamlit Frontend

Bash
streamlit run app/main.py
Author: Prabhav Khare

Specializing in Data Science, Analytics, and applied Machine Learning architectures.
│
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
