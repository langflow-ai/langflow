"""Vectorize the Docusaurus docset into PostgreSQL (pgvector) for RAG.

Uses the same table schema as Langflow's PGVector component, so your Langflow
flow can point its PGVector at this table and answer from the docs.

Usage:
  cd docs/chatbot-proxy
  pip install -r requirements-ingest.txt
  # Set in .env: DATABASE_URL, OPENAI_API_KEY, and optionally DOCS_PATH, COLLECTION_NAME
  python ingest_docs.py

Env:
  DATABASE_URL    Postgres URL (same as proxy). Use ?sslmode=require for DigitalOcean.
  OPENAI_API_KEY  For embeddings (use same model as your Langflow RAG flow, e.g. text-embedding-3-small).
  DOCS_PATH       Path to docs content (default: ../../docs relative to this script, or docs/docs).
  COLLECTION_NAME Table name in Postgres (default: langflow_docs). Set the same in Langflow PGVector.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Default: docs/docs (MDX content) relative to repo docs/ folder
_script_dir = Path(__file__).resolve().parent
DOCS_PATH = os.environ.get("DOCS_PATH") or str(_script_dir.parent / "docs")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME") or "langflow_docs"
DATABASE_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# Set to 1 to delete existing table and re-create (avoids duplicates on re-run)
PRE_DELETE_COLLECTION = os.environ.get("PRE_DELETE_COLLECTION", "").strip().lower() in ("1", "true", "yes")


def _strip_frontmatter(content: str) -> tuple[str, dict]:
    """Return (body, metadata_dict). Metadata may be empty."""
    if not content.startswith("---"):
        return content, {}
    end = content.index("---", 3) if "---" in content[3:] else -1
    if end == -1:
        return content, {}
    head = content[3:end].strip()
    body = content[end + 3 :].lstrip()
    meta = {}
    for line in head.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return body, meta


def load_mdx_md(docs_dir: str) -> list[tuple[str, dict]]:
    """Load .mdx and .md files; return list of (text, metadata)."""
    docs_path = Path(docs_dir)
    if not docs_path.is_dir():
        raise FileNotFoundError(f"DOCS_PATH is not a directory: {docs_dir}")
    out = []
    for ext in ("*.mdx", "*.md"):
        for path in docs_path.rglob(ext):
            if path.name.startswith("_") or "/_partial" in path.as_posix():
                continue
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            body, meta = _strip_frontmatter(raw)
            # Drop MDX/JSX blocks for simpler text (optional: keep for more context)
            body = re.sub(r"<[A-Za-z][^>]*>.*?</[A-Za-z]+>", " ", body, flags=re.DOTALL)
            body = re.sub(r"\{[^}]+\}", " ", body)
            body = re.sub(r"\n{3,}", "\n\n", body).strip()
            if not body:
                continue
            meta["source"] = path.relative_to(docs_path).as_posix()
            meta["title"] = meta.get("title") or path.stem.replace("-", " ").title()
            out.append((body, meta))
    return out


def main() -> None:
    if not DATABASE_URL:
        raise SystemExit("Set DATABASE_URL in .env (e.g. postgresql://user:pass@host:25060/defaultdb?sslmode=require)")
    if not OPENAI_API_KEY:
        raise SystemExit("Set OPENAI_API_KEY in .env")

    # Ensure sslmode for DigitalOcean
    conn_str = DATABASE_URL
    if "postgresql" in conn_str and "sslmode" not in conn_str:
        conn_str = f"{conn_str}&sslmode=require" if "?" in conn_str else f"{conn_str}?sslmode=require"

    from langchain_community.vectorstores import PGVector
    from langchain_core.documents import Document
    from langchain_openai import OpenAIEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    print(f"Loading docs from {DOCS_PATH}...")
    raw_docs = load_mdx_md(DOCS_PATH)
    print(f"Found {len(raw_docs)} files.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )
    documents = []
    for text, meta in raw_docs:
        for chunk in splitter.split_text(text):
            documents.append(Document(page_content=chunk, metadata=dict(meta)))

    print(f"Split into {len(documents)} chunks. Embedding and storing in table '{COLLECTION_NAME}'...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    PGVector.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        connection_string=conn_str,
        use_jsonb=True,
        pre_delete_collection=PRE_DELETE_COLLECTION,
    )
    print("Done. In Langflow, set the PGVector component to this table name and the same connection string.")
    if not PRE_DELETE_COLLECTION:
        print("Tip: set PRE_DELETE_COLLECTION=1 to replace the table on the next run (no duplicates).")


if __name__ == "__main__":
    main()
