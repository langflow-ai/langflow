import json
import shutil
from http import HTTPStatus
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases")

KNOWLEDGE_BASES_DIR = "~/.langflow/knowledge_bases"


class KnowledgeBaseInfo(BaseModel):
    id: str
    name: str
    embedding_provider: str | None = "Unknown"
    embedding_model: str | None = "Unknown"
    size: int = 0
    words: int = 0
    characters: int = 0
    chunks: int = 0
    avg_chunk_size: float = 0.0


class BulkDeleteRequest(BaseModel):
    kb_names: list[str]


def get_kb_root_path() -> Path:
    """Get the knowledge bases root path."""
    return Path(KNOWLEDGE_BASES_DIR).expanduser()


def get_directory_size(path: Path) -> int:
    """Calculate the total size of all files in a directory."""
    total_size = 0
    try:
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except (OSError, PermissionError):
        pass
    return total_size


def detect_embedding_provider(kb_path: Path) -> str:
    """Detect the embedding provider from config files and directory structure."""
    # Provider patterns to check for
    provider_patterns = {
        "OpenAI": ["openai", "text-embedding-ada", "text-embedding-3"],
        "HuggingFace": ["sentence-transformers", "huggingface", "bert-"],
        "Cohere": ["cohere", "embed-english", "embed-multilingual"],
        "Google": ["palm", "gecko", "google"],
        "Chroma": ["chroma"],
    }

    # Check JSON config files for provider information
    for config_file in kb_path.glob("*.json"):
        try:
            with config_file.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
                if not isinstance(config_data, dict):
                    continue

                config_str = json.dumps(config_data).lower()

                # Check for explicit provider fields first
                provider_fields = ["embedding_provider", "provider", "embedding_model_provider"]
                for field in provider_fields:
                    if field in config_data:
                        provider_value = str(config_data[field]).lower()
                        for provider, patterns in provider_patterns.items():
                            if any(pattern in provider_value for pattern in patterns):
                                return provider

                # Check for model name patterns
                for provider, patterns in provider_patterns.items():
                    if any(pattern in config_str for pattern in patterns):
                        return provider

        except (OSError, json.JSONDecodeError) as _:
            import logging

            logging.exception("Error reading config file '%s'", config_file)
            continue

    # Fallback to directory structure
    if (kb_path / "chroma").exists():
        return "Chroma"
    if (kb_path / "vectors.npy").exists():
        return "Local"

    return "Unknown"


def detect_embedding_model(kb_path: Path) -> str:
    """Detect the embedding model from config files."""
    # First check the embedding metadata file (most accurate)
    metadata_file = kb_path / "embedding_metadata.json"
    if metadata_file.exists():
        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
                if isinstance(metadata, dict):
                    # Check for embedding model field
                    if "embedding_model" in metadata:
                        model_value = str(metadata["embedding_model"])
                        if model_value and model_value.lower() != "unknown":
                            return model_value
        except (OSError, json.JSONDecodeError) as _:
            import logging
            logging.exception("Error reading embedding metadata file '%s'", metadata_file)

    # Check other JSON config files for model information
    for config_file in kb_path.glob("*.json"):
        # Skip the embedding metadata file since we already checked it
        if config_file.name == "embedding_metadata.json":
            continue
            
        try:
            with config_file.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
                if not isinstance(config_data, dict):
                    continue

                # Check for explicit model fields first and return the actual model name
                model_fields = ["embedding_model", "model", "embedding_model_name", "model_name"]
                for field in model_fields:
                    if field in config_data:
                        model_value = str(config_data[field])
                        if model_value and model_value.lower() != "unknown":
                            return model_value

                # Check for OpenAI specific model names
                if "openai" in json.dumps(config_data).lower():
                    openai_models = ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"]
                    config_str = json.dumps(config_data).lower()
                    for model in openai_models:
                        if model in config_str:
                            return model

                # Check for HuggingFace model names (usually in model field)
                if "model" in config_data:
                    model_name = str(config_data["model"])
                    # Common HuggingFace embedding models
                    hf_patterns = ["sentence-transformers", "all-MiniLM", "all-mpnet", "multi-qa"]
                    if any(pattern in model_name for pattern in hf_patterns):
                        return model_name

        except (OSError, json.JSONDecodeError) as _:
            import logging

            logging.exception("Error reading config file '%s'", config_file)
            continue

    return "Unknown"


def get_text_columns(df: pd.DataFrame, schema_data: list | None = None) -> list[str]:
    """Get the text columns to analyze for word/character counts."""
    # First try schema-defined text columns
    if schema_data:
        text_columns = [
            col["column_name"]
            for col in schema_data
            if col.get("vectorize", False) and col.get("data_type") == "string"
        ]
        if text_columns:
            return [col for col in text_columns if col in df.columns]

    # Fallback to common text column names
    common_names = ["text", "content", "document", "chunk"]
    text_columns = [col for col in df.columns if col.lower() in common_names]
    if text_columns:
        return text_columns

    # Last resort: all string columns
    return [col for col in df.columns if df[col].dtype == "object"]


def calculate_text_metrics(df: pd.DataFrame, text_columns: list[str]) -> tuple[int, int]:
    """Calculate total words and characters from text columns."""
    total_words = 0
    total_characters = 0

    for col in text_columns:
        if col not in df.columns:
            continue

        text_series = df[col].astype(str).fillna("")
        total_characters += text_series.str.len().sum()
        total_words += text_series.str.split().str.len().sum()

    return int(total_words), int(total_characters)


def get_kb_metadata(kb_path: Path) -> dict:
    """Extract metadata from a knowledge base directory."""
    metadata: dict[str, float | int | str] = {
        "chunks": 0,
        "words": 0,
        "characters": 0,
        "avg_chunk_size": 0.0,
        "embedding_provider": "Unknown",
        "embedding_model": "Unknown",
    }

    try:
        # First check embedding metadata file for accurate provider and model info
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            try:
                with metadata_file.open("r", encoding="utf-8") as f:
                    embedding_metadata = json.load(f)
                    if isinstance(embedding_metadata, dict):
                        if "embedding_provider" in embedding_metadata:
                            metadata["embedding_provider"] = embedding_metadata["embedding_provider"]
                        if "embedding_model" in embedding_metadata:
                            metadata["embedding_model"] = embedding_metadata["embedding_model"]
            except (OSError, json.JSONDecodeError) as _:
                import logging
                logging.exception("Error reading embedding metadata file '%s'", metadata_file)

        # Fallback to detection if not found in metadata file
        if metadata["embedding_provider"] == "Unknown":
            metadata["embedding_provider"] = detect_embedding_provider(kb_path)
        if metadata["embedding_model"] == "Unknown":
            metadata["embedding_model"] = detect_embedding_model(kb_path)

        # Read schema for text column information
        schema_data = None
        schema_file = kb_path / "schema.json"
        if schema_file.exists():
            try:
                with schema_file.open("r", encoding="utf-8") as f:
                    schema_data = json.load(f)
                    if not isinstance(schema_data, list):
                        schema_data = None
            except (ValueError, TypeError, OSError) as _:
                import logging

                logging.exception("Error reading schema file '%s'", schema_file)

        # Process source.parquet for text metrics
        source_file = kb_path / "source.parquet"
        if source_file.exists():
            try:
                source_chunks = pd.DataFrame(pd.read_parquet(source_file))
                metadata["chunks"] = len(source_chunks)

                # Get text columns and calculate metrics
                text_columns = get_text_columns(source_chunks, schema_data)
                if text_columns:
                    words, characters = calculate_text_metrics(source_chunks, text_columns)
                    metadata["words"] = words
                    metadata["characters"] = characters

                    # Calculate average chunk size
                    if int(metadata["chunks"]) > 0:
                        metadata["avg_chunk_size"] = round(int(characters) / int(metadata["chunks"]), 1)

            except (OSError, ValueError, TypeError) as _:
                import logging

                logging.exception("Error processing source.parquet file '%s'", source_file)

    except Exception as _:
        import logging

        logging.exception("Error processing knowledge base directory '%s'", kb_path)

    return metadata


@router.get("", status_code=HTTPStatus.OK)
@router.get("/", status_code=HTTPStatus.OK)
async def list_knowledge_bases() -> list[KnowledgeBaseInfo]:
    """List all available knowledge bases."""
    try:
        kb_root_path = get_kb_root_path()

        if not kb_root_path.exists():
            return []

        knowledge_bases = []

        for kb_dir in kb_root_path.iterdir():
            if not kb_dir.is_dir() or kb_dir.name.startswith("."):
                continue

            try:
                # Get size of the directory
                size = get_directory_size(kb_dir)

                # Get metadata from KB files
                metadata = get_kb_metadata(kb_dir)

                kb_info = KnowledgeBaseInfo(
                    id=kb_dir.name,
                    name=kb_dir.name.replace("_", " ").replace("-", " ").title(),
                    embedding_provider=metadata["embedding_provider"],
                    embedding_model=metadata["embedding_model"],
                    size=size,
                    words=metadata["words"],
                    characters=metadata["characters"],
                    chunks=metadata["chunks"],
                    avg_chunk_size=metadata["avg_chunk_size"],
                )

                knowledge_bases.append(kb_info)

            except OSError as _:
                # Log the exception and skip directories that can't be read
                import logging

                logging.exception("Error reading knowledge base directory '%s'", kb_dir)
                continue

        # Sort by name alphabetically
        knowledge_bases.sort(key=lambda x: x.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing knowledge bases: {e!s}") from e
    else:
        return knowledge_bases


@router.get("/{kb_name}", status_code=HTTPStatus.OK)
async def get_knowledge_base(kb_name: str) -> KnowledgeBaseInfo:
    """Get detailed information about a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_path = kb_root_path / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Get size of the directory
        size = get_directory_size(kb_path)

        # Get metadata from KB files
        metadata = get_kb_metadata(kb_path)

        return KnowledgeBaseInfo(
            id=kb_name,
            name=kb_name.replace("_", " ").replace("-", " ").title(),
            embedding_provider=metadata["embedding_provider"],
            embedding_model=metadata["embedding_model"],
            size=size,
            words=metadata["words"],
            characters=metadata["characters"],
            chunks=metadata["chunks"],
            avg_chunk_size=metadata["avg_chunk_size"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting knowledge base '{kb_name}': {e!s}") from e


@router.delete("/{kb_name}", status_code=HTTPStatus.OK)
async def delete_knowledge_base(kb_name: str) -> dict[str, str]:
    """Delete a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_path = kb_root_path / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Delete the entire knowledge base directory
        shutil.rmtree(kb_path)

        return {"message": f"Knowledge base '{kb_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting knowledge base '{kb_name}': {e!s}") from e


@router.delete("", status_code=HTTPStatus.OK)
@router.delete("/", status_code=HTTPStatus.OK)
async def delete_knowledge_bases_bulk(request: BulkDeleteRequest) -> dict[str, str | int]:
    """Delete multiple knowledge bases."""
    try:
        kb_root_path = get_kb_root_path()
        deleted_count = 0
        not_found_kbs = []

        for kb_name in request.kb_names:
            kb_path = kb_root_path / kb_name
            
            if not kb_path.exists() or not kb_path.is_dir():
                not_found_kbs.append(kb_name)
                continue

            try:
                # Delete the entire knowledge base directory
                shutil.rmtree(kb_path)
                deleted_count += 1
            except Exception as e:
                import logging
                logging.exception("Error deleting knowledge base '%s': %s", kb_name, e)
                # Continue with other deletions even if one fails

        if not_found_kbs and deleted_count == 0:
            raise HTTPException(
                status_code=404, 
                detail=f"Knowledge bases not found: {', '.join(not_found_kbs)}"
            )

        result = {
            "message": f"Successfully deleted {deleted_count} knowledge base(s)",
            "deleted_count": deleted_count,
        }

        if not_found_kbs:
            result["not_found"] = not_found_kbs

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting knowledge bases: {e!s}") from e
