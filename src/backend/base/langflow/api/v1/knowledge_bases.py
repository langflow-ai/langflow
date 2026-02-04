import json
import shutil
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.log import logger
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_settings_service

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases")


_KNOWLEDGE_BASES_DIR: Path | None = None


def _get_knowledge_bases_dir() -> Path:
    """Lazy load the knowledge bases directory from settings."""
    global _KNOWLEDGE_BASES_DIR  # noqa: PLW0603
    if _KNOWLEDGE_BASES_DIR is None:
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        _KNOWLEDGE_BASES_DIR = Path(knowledge_directory).expanduser()
    return _KNOWLEDGE_BASES_DIR


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


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    embedding_provider: str
    embedding_model: str


class AddSourceRequest(BaseModel):
    source_name: str
    files: list[str]  # List of file paths or file IDs


class ChunkInfo(BaseModel):
    id: str
    content: str
    char_count: int
    metadata: dict | None = None


def get_kb_root_path() -> Path:
    """Get the knowledge bases root path."""
    return _get_knowledge_bases_dir()


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
            logger.exception("Error reading config file '%s'", config_file)
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
                if isinstance(metadata, dict) and "embedding_model" in metadata:
                    # Check for embedding model field
                    model_value = str(metadata.get("embedding_model", "unknown"))
                    if model_value and model_value.lower() != "unknown":
                        return model_value
        except (OSError, json.JSONDecodeError) as _:
            logger.exception("Error reading embedding metadata file '%s'", metadata_file)

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
            logger.exception("Error reading config file '%s'", config_file)
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
        total_characters += int(text_series.str.len().sum())
        total_words += int(text_series.str.split().str.len().sum())

    return total_words, total_characters


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
                logger.exception("Error reading embedding metadata file '%s'", metadata_file)

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
                logger.exception("Error reading schema file '%s'", schema_file)

        # Create vector store
        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=kb_path.name,
        )

        # Access the raw collection
        collection = chroma._collection  # noqa: SLF001

        # Fetch all documents and metadata
        results = collection.get(include=["documents", "metadatas"])

        # Convert to pandas DataFrame
        source_chunks = pd.DataFrame(
            {
                "document": results["documents"],
                "metadata": results["metadatas"],
            }
        )

        # Process the source data for metadata
        try:
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
            logger.exception("Error processing Chroma DB '%s'", kb_path.name)

    except (OSError, ValueError, TypeError) as _:
        logger.exception("Error processing knowledge base directory '%s'", kb_path)

    return metadata


@router.post("", status_code=HTTPStatus.CREATED)
@router.post("/", status_code=HTTPStatus.CREATED)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseInfo:
    """Create a new knowledge base with embedding configuration."""
    from datetime import datetime, timezone

    from langflow.services.auth.utils import encrypt_api_key

    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_name = request.name.strip().replace(" ", "_")

        # Validate KB name
        if not kb_name or len(kb_name) < 3:
            raise HTTPException(status_code=400, detail="Knowledge base name must be at least 3 characters")

        kb_path = kb_root_path / kb_user / kb_name

        # Check if KB already exists
        if kb_path.exists():
            raise HTTPException(status_code=409, detail=f"Knowledge base '{kb_name}' already exists")

        # Create KB directory
        kb_path.mkdir(parents=True, exist_ok=True)

        # Save embedding metadata
        embedding_metadata = {
            "embedding_provider": request.embedding_provider,
            "embedding_model": request.embedding_model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        metadata_path = kb_path / "embedding_metadata.json"
        metadata_path.write_text(json.dumps(embedding_metadata, indent=2))

        return KnowledgeBaseInfo(
            id=kb_name,
            name=kb_name.replace("_", " ").replace("-", " "),
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model,
            size=0,
            words=0,
            characters=0,
            chunks=0,
            avg_chunk_size=0.0,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up if something went wrong
        if kb_path.exists():
            shutil.rmtree(kb_path)
        raise HTTPException(status_code=500, detail=f"Error creating knowledge base: {e!s}") from e


@router.post("/{kb_name}/ingest", status_code=HTTPStatus.OK)
async def ingest_files_to_knowledge_base(
    kb_name: str,
    current_user: CurrentActiveUser,
    files: Annotated[list[UploadFile], File(description="Files to ingest into the knowledge base")],
    source_name: Annotated[str, Form()] = "",
    chunk_size: Annotated[int, Form()] = 1000,
    chunk_overlap: Annotated[int, Form()] = 200,
) -> dict[str, object]:
    """Upload and ingest files directly into a knowledge base.

    This endpoint:
    1. Accepts file uploads
    2. Extracts text and chunks the content
    3. Creates embeddings using the KB's configured embedding model
    4. Stores the vectors in the knowledge base
    """
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Read embedding metadata
        metadata_path = kb_path / "embedding_metadata.json"
        if not metadata_path.exists():
            raise HTTPException(status_code=400, detail="Knowledge base missing embedding configuration")

        embedding_metadata = json.loads(metadata_path.read_text())
        embedding_provider = embedding_metadata.get("embedding_provider")
        embedding_model = embedding_metadata.get("embedding_model")

        if not embedding_provider or not embedding_model:
            raise HTTPException(status_code=400, detail="Invalid embedding configuration")

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Process uploaded files and create documents
        documents = []
        processed_files = []
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for uploaded_file in files:
            try:
                # Read file content
                file_content = await uploaded_file.read()
                file_name = uploaded_file.filename or "unknown"

                # Decode text content
                text_content = file_content.decode("utf-8", errors="ignore")

                if not text_content.strip():
                    await logger.awarning(f"File {file_name} is empty or not readable as text")
                    continue

                # Split into chunks
                chunks = text_splitter.split_text(text_content)

                # Create documents from chunks
                for i, chunk in enumerate(chunks):
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "source": source_name or file_name,
                            "file_name": file_name,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "ingested_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    documents.append(doc)

                processed_files.append(file_name)

            except Exception as file_error:
                await logger.awarning(f"Error processing file {uploaded_file.filename}: {file_error}")
                continue

        if not documents:
            raise HTTPException(status_code=400, detail="No valid content extracted from files")

        # Build embeddings based on provider
        embeddings = _build_embeddings(embedding_provider, embedding_model, current_user)

        # Create or update vector store
        chroma = Chroma(
            persist_directory=str(kb_path),
            embedding_function=embeddings,
            collection_name=kb_name,
        )

        # Add documents to vector store
        chroma.add_documents(documents)

        return {
            "message": f"Successfully ingested {len(processed_files)} file(s) with {len(documents)} chunks into '{kb_name}'",
            "files_processed": len(processed_files),
            "chunks_created": len(documents),
            "file_names": processed_files,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting files to knowledge base: {e!s}") from e


def _build_embeddings(provider: str, model: str, current_user):
    """Build embedding model based on provider configuration."""
    from langflow.services.deps import get_variable_service
    from langflow.services.database.utils import session_scope

    # Get API key from global variables based on provider
    provider_key_mapping = {
        "OpenAI": "OPENAI_API_KEY",
        "Cohere": "COHERE_API_KEY",
        "HuggingFace": "HUGGINGFACEHUB_API_TOKEN",
        "Google": "GOOGLE_API_KEY",
    }

    variable_name = provider_key_mapping.get(provider)
    api_key = None

    if variable_name:
        import asyncio

        async def get_api_key():
            variable_service = get_variable_service()
            async with session_scope() as session:
                try:
                    return await variable_service.get_variable(
                        user_id=current_user.id,
                        name=variable_name,
                        field="",
                        session=session,
                    )
                except Exception:
                    return None

        api_key = asyncio.get_event_loop().run_until_complete(get_api_key())

    if provider == "OpenAI":
        from langchain_openai import OpenAIEmbeddings

        if not api_key:
            raise ValueError("OpenAI API key not configured. Please set up the provider in settings.")
        return OpenAIEmbeddings(model=model, api_key=api_key)

    elif provider == "HuggingFace":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=model)

    elif provider == "Cohere":
        from langchain_cohere import CohereEmbeddings

        if not api_key:
            raise ValueError("Cohere API key not configured. Please set up the provider in settings.")
        return CohereEmbeddings(model=model, cohere_api_key=api_key)

    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")


@router.get("", status_code=HTTPStatus.OK)
@router.get("/", status_code=HTTPStatus.OK)
async def list_knowledge_bases(current_user: CurrentActiveUser) -> list[KnowledgeBaseInfo]:
    """List all available knowledge bases."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user

        if not kb_path.exists():
            return []

        knowledge_bases = []

        for kb_dir in kb_path.iterdir():
            if not kb_dir.is_dir() or kb_dir.name.startswith("."):
                continue

            try:
                # Get size of the directory
                size = get_directory_size(kb_dir)

                # Get metadata from KB files
                metadata = get_kb_metadata(kb_dir)

                kb_info = KnowledgeBaseInfo(
                    id=kb_dir.name,
                    name=kb_dir.name.replace("_", " ").replace("-", " "),
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
                await logger.aexception("Error reading knowledge base directory '%s'", kb_dir)
                continue

        # Sort by name alphabetically
        knowledge_bases.sort(key=lambda x: x.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing knowledge bases: {e!s}") from e
    else:
        return knowledge_bases


@router.get("/{kb_name}", status_code=HTTPStatus.OK)
async def get_knowledge_base(kb_name: str, current_user: CurrentActiveUser) -> KnowledgeBaseInfo:
    """Get detailed information about a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Get size of the directory
        size = get_directory_size(kb_path)

        # Get metadata from KB files
        metadata = get_kb_metadata(kb_path)

        return KnowledgeBaseInfo(
            id=kb_name,
            name=kb_name.replace("_", " ").replace("-", " "),
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


@router.get("/{kb_name}/chunks", status_code=HTTPStatus.OK)
async def get_knowledge_base_chunks(kb_name: str, current_user: CurrentActiveUser) -> list[ChunkInfo]:
    """Get all chunks from a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Create vector store
        chroma = Chroma(
            persist_directory=str(kb_path),
            collection_name=kb_name,
        )

        # Access the raw collection
        collection = chroma._collection  # noqa: SLF001

        # Fetch all documents and metadata
        results = collection.get(include=["documents", "metadatas"])

        chunks = []
        for i, (doc_id, document, metadata) in enumerate(
            zip(results["ids"], results["documents"], results["metadatas"], strict=False)
        ):
            content = document or ""
            chunks.append(
                ChunkInfo(
                    id=doc_id,
                    content=content,
                    char_count=len(content),
                    metadata=metadata,
                )
            )

        return chunks

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chunks for '{kb_name}': {e!s}") from e


@router.delete("/{kb_name}", status_code=HTTPStatus.OK)
async def delete_knowledge_base(kb_name: str, current_user: CurrentActiveUser) -> dict[str, str]:
    """Delete a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_path = kb_root_path / kb_user / kb_name

        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        # Delete the entire knowledge base directory
        shutil.rmtree(kb_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting knowledge base '{kb_name}': {e!s}") from e
    else:
        return {"message": f"Knowledge base '{kb_name}' deleted successfully"}


@router.delete("", status_code=HTTPStatus.OK)
@router.delete("/", status_code=HTTPStatus.OK)
async def delete_knowledge_bases_bulk(request: BulkDeleteRequest, current_user: CurrentActiveUser) -> dict[str, object]:
    """Delete multiple knowledge bases."""
    try:
        kb_root_path = get_kb_root_path()
        kb_user = current_user.username
        kb_user_path = kb_root_path / kb_user
        deleted_count = 0
        not_found_kbs = []

        for kb_name in request.kb_names:
            kb_path = kb_user_path / kb_name

            if not kb_path.exists() or not kb_path.is_dir():
                not_found_kbs.append(kb_name)
                continue

            try:
                # Delete the entire knowledge base directory
                shutil.rmtree(kb_path)
                deleted_count += 1
            except (OSError, PermissionError) as e:
                await logger.aexception("Error deleting knowledge base '%s': %s", kb_name, e)
                # Continue with other deletions even if one fails

        if not_found_kbs and deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Knowledge bases not found: {', '.join(not_found_kbs)}")

        result = {
            "message": f"Successfully deleted {deleted_count} knowledge base(s)",
            "deleted_count": deleted_count,
        }

        if not_found_kbs:
            result["not_found"] = ", ".join(not_found_kbs)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting knowledge bases: {e!s}") from e
    else:
        return result
