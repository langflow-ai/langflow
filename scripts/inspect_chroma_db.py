"""Script to inspect ChromaDB database contents.

Displays statistics and document values (truncated to 200 chars).

Usage:
    python scripts/inspect_chroma_db.py /path/to/chroma/db
"""

import sys
from pathlib import Path

try:
    import chromadb
except ImportError:
    print("Error: chromadb not installed. Install with: pip install chromadb")
    sys.exit(1)


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length characters."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def inspect_chroma_db(db_path: str) -> None:
    """Inspect and display ChromaDB contents."""
    db_path_obj = Path(db_path)

    if not db_path_obj.exists():
        print(f"Error: Path does not exist: {db_path}")
        sys.exit(1)

    print(f"Inspecting ChromaDB at: {db_path}")
    print("=" * 80)

    try:
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(path=str(db_path_obj))

        # Get all collections
        collections = client.list_collections()

        if not collections:
            print("No collections found in the database.")
            return

        print(f"\nTotal Collections: {len(collections)}")
        print("=" * 80)

        # Iterate through each collection
        for idx, collection in enumerate(collections, 1):
            print(f"\n[Collection {idx}] {collection.name}")
            print("-" * 80)

            # Get collection metadata
            metadata = collection.metadata
            if metadata:
                print(f"Metadata: {metadata}")

            # Get collection count
            count = collection.count()
            print(f"Total Documents: {count}")

            if count == 0:
                print("  (empty collection)")
                continue

            # Get all documents (with limit for safety)
            max_docs = min(count, 100)  # Limit to 100 docs for display
            results = collection.get(
                limit=max_docs,
                include=["documents", "metadatas", "embeddings"]
            )

            print(f"\nShowing {len(results['ids'])} of {count} documents:")
            print("-" * 80)

            # Display each document
            for i, doc_id in enumerate(results["ids"], 1):
                print(f"\n  Document {i}:")
                print(f"    ID: {doc_id}")

                # Document text
                if results["documents"] and i-1 < len(results["documents"]):
                    doc_text = results["documents"][i-1]
                    if doc_text:
                        truncated = truncate_text(doc_text, 2000)
                        print(f"    Text: {truncated}")

                # Metadata
                if results["metadatas"] and i-1 < len(results["metadatas"]):
                    doc_metadata = results["metadatas"][i-1]
                    if doc_metadata:
                        print(f"    Metadata: {doc_metadata}")

                # Embedding info (just dimensions, not full vector)
                if results["embeddings"] is not None and i-1 < len(results["embeddings"]):
                    embedding = results["embeddings"][i-1]
                    if embedding is not None:
                        print(f"    Embedding: {len(embedding)} dimensions")

            if count > max_docs:
                print(f"\n  ... and {count - max_docs} more documents")

        print("\n" + "=" * 80)
        print("Inspection complete!")

    except Exception as e:  # noqa: BLE001
        print(f"Error inspecting database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    _expected_argc = 2
    if len(sys.argv) != _expected_argc:
        print("Usage: python scripts/inspect_chroma_db.py /path/to/chroma/db")
        sys.exit(1)

    db_path = sys.argv[1]
    inspect_chroma_db(db_path)


if __name__ == "__main__":
    main()

# Made with Bob
