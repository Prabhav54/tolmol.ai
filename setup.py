from pathlib import Path

from setuptools import find_packages, setup

requirements = [
    line.strip()
    for line in Path(__file__).with_name("requirements.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]

setup(
    name="tolmol-ai",
    version="2.0.0",
    description="Hybrid RAG e-commerce search: pgvector semantic retrieval + SQL constraint filtering.",
    author="Prabhav Khare",
    packages=find_packages(include=["api*", "benchmark*", "core*", "db*", "engines*", "scraper*", "scripts*"]),
    python_requires=">=3.9",
    install_requires=requirements,
)
