import os
from setuptools import setup, find_packages

# Read the requirements.txt safely to populate dependencies dynamically
def read_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    # Fallback to hardcoded requirements if file is not found natively
    return [
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "sqlalchemy>=2.0.0",
        "pgvector>=0.2.0",
        "sentence-transformers>=2.2.2",
        "huggingface_hub>=0.16.4",
        "python-dotenv>=1.0.0",
        "beautifulsoup4>=4.12.2",
        "requests>=2.31.0",
        "pandas>=2.0.0",
        "streamlit>=1.24.0"
    ]

setup(
    name="hybrid-rag-ecommerce",
    version="1.0.0",
    description="Dynamic Hybrid RAG E-Commerce Intelligence Platform combining Text-to-SQL and Vector Proximity Engines over pgvector.",
    author="Prabhav Khare",
    packages=find_packages(include=["core", "core.*", "db", "db.*", "scraper", "scraper.*", "engines", "engines.*", "api", "api.*"]),
    python_requires=">=3.9",
    install_requires=read_requirements(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Artificial Intelligence"
    ],
)