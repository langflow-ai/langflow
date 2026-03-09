import asyncio
import contextlib
import gc
import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import platform
import time
from typing import Optional, Dict, Any
import weakref
import shutil

import chromadb
import chromadb.errors
import pandas as pd
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.base.data.utils import extract_text_from_bytes
from lfx.base.models.unified_models import get_embedding_model_options
from lfx.components.models_and_agents.embedding_model import EmbeddingModelComponent
from lfx.log import logger

from langflow.api.utils import CurrentActiveUser
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_settings_service
from langflow.services.jobs.service import JobService
from langflow.utils.kb_constants import (
    EXPONENTIAL_BACKOFF_MULTIPLIER,
    INGESTION_BATCH_SIZE,
    MAX_RETRY_ATTEMPTS,
)


class IngestionCancelledError(Exception):
    """Custom error for when an ingestion job is cancelled."""


class ChromaConnectionManager:
    """
    Singleton manager for ChromaDB connections to prevent file locks on Windows.
    Ensures proper cleanup of connections and handles Windows-specific issues.
    """
    _instance = None
    _connections: Dict[str, weakref.ref] = {}
    _clients: Dict[str, chromadb.PersistentClient] = {}
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._connections = {}
            self._clients = {}
            self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        return cls()
    
    def close_connection(self, kb_path: str, force: bool = False) -> None:
        """
        Close a specific ChromaDB connection.
        
        Args:
            kb_path: Path to the knowledge base
            force: If True, force close even if references exist
        """
        path_key = str(kb_path)
        
        # Close Chroma wrapper if it exists
        if path_key in self._connections:
            chroma_ref = self._connections.get(path_key)
            if chroma_ref:
                chroma = chroma_ref()
                if chroma:
                    try:
                        # Try to delete collection to release resources
                        with contextlib.suppress(Exception):
                            chroma._collection = None  # Clear collection reference
                        chroma = None
                    except Exception as e:
                        logger.debug(f"Error closing Chroma wrapper for {path_key}: {e}")
            del self._connections[path_key]
        
        # Close underlying client
        if path_key in self._clients:
            try:
                client = self._clients[path_key]
                # Clear from ChromaDB's internal registry
                if path_key in SharedSystemClient._identifier_to_system:
                    del SharedSystemClient._identifier_to_system[path_key]
                # SQLite specific cleanup for Windows
                if platform.system() == "Windows" and hasattr(client, '_db'):
                    try:
                        client._db.close()
                    except:
                        pass
                del self._clients[path_key]
            except Exception as e:
                logger.debug(f"Error closing ChromaDB client for {path_key}: {e}")
        
        # Force garbage collection to release file handles
        gc.collect()
        
        # On Windows, give the OS time to release file handles
        if platform.system() == "Windows":
            time.sleep(0.1)
    
    def close_all_connections(self) -> None:
        """Close all open ChromaDB connections."""
        paths_to_close = list(self._clients.keys()) + list(self._connections.keys())
        for path_key in set(paths_to_close):
            self.close_connection(path_key, force=True)
    
    def get_client(self, kb_path: Path) -> chromadb.PersistentClient:
        """
        Get or create a ChromaDB client with proper connection management.
        
        Args:
            kb_path: Path to the knowledge base
            
        Returns:
            ChromaDB PersistentClient
        """
        path_key = str(kb_path)
        
        # Close any existing connection first (Windows fix)
        if platform.system() == "Windows" and path_key in self._clients:
            self.close_connection(kb_path, force=True)
        
        # Clear ChromaDB's internal registry
        if path_key in SharedSystemClient._identifier_to_system:
            try:
                del SharedSystemClient._identifier_to_system[path_key]
            except KeyError:
                pass
        
        # Create new client with unique session ID
        client = chromadb.PersistentClient(
            path=path_key,
            settings=Settings(
                is_persistent=True,
                persist_directory=path_key,
                chroma_otel_service_name=str(uuid.uuid4()),
                # Windows-specific settings to reduce lock duration
                chroma_db_impl="sqlite" if platform.system() == "Windows" else "duckdb+parquet",
            ),
        )
        
        self._clients[path_key] = client
        return client
    
    def get_chroma(self, kb_path: Path, kb_name: str, create_if_not_exists: bool = False) -> Optional[Chroma]:
        """
        Get a Chroma wrapper with managed connection.
        
        Args:
            kb_path: Path to the knowledge base
            kb_name: Name of the knowledge base
            create_if_not_exists: Whether to create collection if it doesn't exist
            
        Returns:
            Chroma wrapper or None if not exists and create_if_not_exists is False
        """
        path_key = str(kb_path)
        
        # Check if we have an existing connection
        if path_key in self._connections:
            chroma_ref = self._connections.get(path_key)
            if chroma_ref:
                chroma = chroma_ref()
                if chroma:
                    return chroma
        
        # Get or create client
        client = self.get_client(kb_path)
        
        # Check if collection exists
        collections = client.list_collections()
        collection_exists = any(c.name == kb_name for c in collections)
        
        if not collection_exists and not create_if_not_exists:
            return None
        
        # Create Chroma wrapper
        try:
            chroma = Chroma(
                client=client,
                collection_name=kb_name,
            )
            # Store weak reference to allow garbage collection
            self._connections[path_key] = weakref.ref(chroma)
            return chroma
        except Exception as e:
            logger.error(f"Error creating Chroma wrapper for {kb_name}: {e}")
            return None


class KBStorageHelper:
    """Helper class for Knowledge Base storage and path management with Windows fixes."""
    
    # Use the connection manager singleton
    _connection_manager = ChromaConnectionManager.get_instance()
    
    @staticmethod
    @lru_cache
    def get_root_path() -> Path:
        """Lazy load and return the knowledge bases root directory."""
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        return Path(knowledge_directory).expanduser()

    @staticmethod
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

    @staticmethod
    def get_fresh_chroma_client(kb_path: Path) -> chromadb.PersistentClient:
        """
        Get a fresh Chroma client with proper connection management.
        This method ensures connections are properly managed to prevent Windows file locks.
        """
        return KBStorageHelper._connection_manager.get_client(kb_path)
    
    @staticmethod
    def get_managed_chroma(kb_path: Path, kb_name: str, create_if_not_exists: bool = False) -> Optional[Chroma]:
        """
        Get a managed Chroma wrapper that will be properly cleaned up.
        
        Args:
            kb_path: Path to the knowledge base
            kb_name: Name of the knowledge base
            create_if_not_exists: Whether to create collection if it doesn't exist
            
        Returns:
            Chroma wrapper or None
        """
        return KBStorageHelper._connection_manager.get_chroma(kb_path, kb_name, create_if_not_exists)
    
    @staticmethod
    def close_connection(kb_path: Path) -> None:
        """
        Close ChromaDB connection for a specific knowledge base.
        
        Args:
            kb_path: Path to the knowledge base
        """
        KBStorageHelper._connection_manager.close_connection(str(kb_path))

    @staticmethod
    def teardown_storage(kb_path: Path, kb_name: str) -> None:
        """
        Explicitly flush and invalidate Chroma clients before directory deletion.
        Enhanced for Windows with multiple cleanup strategies.
        """
        try:
            # First, close any managed connections
            KBStorageHelper._connection_manager.close_connection(str(kb_path), force=True)
            
            # Check if ChromaDB data exists
            has_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
            if not has_data:
                return
            
            # Try to delete the collection through ChromaDB
            try:
                client = KBStorageHelper.get_fresh_chroma_client(kb_path)
                collections = client.list_collections()
                for collection in collections:
                    if collection.name == kb_name:
                        try:
                            client.delete_collection(kb_name)
                        except Exception as e:
                            logger.debug(f"Error deleting collection {kb_name}: {e}")
                
                # Close the client
                KBStorageHelper._connection_manager.close_connection(str(kb_path), force=True)
                
            except Exception as e:
                logger.debug(f"Error during collection deletion for {kb_name}: {e}")
            
            # Windows-specific: Try to remove lock files
            if platform.system() == "Windows":
                # Give Windows time to release handles
                time.sleep(0.5)
                
                # Try to remove SQLite lock files
                for lock_file in kb_path.glob("*.sqlite3-*"):  # WAL, SHM files
                    try:
                        lock_file.unlink()
                    except:
                        pass
                
                # Try to truncate SQLite files
                for sqlite_file in kb_path.glob("*.sqlite3"):
                    try:
                        # Truncating can sometimes release locks
                        with open(sqlite_file, 'r+b') as f:
                            f.truncate(0)
                    except:
                        pass
            
            # Final cleanup
            gc.collect()
            
            # Extra wait on Windows
            if platform.system() == "Windows":
                time.sleep(0.5)
                
        except Exception as e:
            logger.debug(f"Storage teardown failed for {kb_path.name}: {e}")


class KBAnalysisHelper:
    """Helper class for Knowledge Base metadata, metrics, and configuration detection."""

    @staticmethod
    def get_metadata(kb_path: Path, *, fast: bool = False) -> dict:
        """Extract metadata from a knowledge base directory."""
        metadata_file = kb_path / "embedding_metadata.json"
        defaults = {
            "chunks": 0,
            "words": 0,
            "characters": 0,
            "avg_chunk_size": 0.0,
            "embedding_provider": "Unknown",
            "embedding_model": "Unknown",
            "id": str(uuid.uuid4()),
            "size": 0,
            "source_types": [],
            "chunk_size": None,
            "chunk_overlap": None,
            "separator": None,
        }

        metadata = {}
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
            except (OSError, json.JSONDecodeError):
                logger.warning(f"Failed to parse metadata file for {kb_path.name}, resetting to defaults.")

        missing_keys = not all(k in metadata for k in defaults)
        has_unknowns = metadata.get("embedding_provider") == "Unknown" or metadata.get("embedding_model") == "Unknown"

        if fast and not missing_keys:
            return metadata

        backfill_needed = not metadata_file.exists() or missing_keys or (not fast and has_unknowns)

        if backfill_needed:
            for key, default_val in defaults.items():
                if key not in metadata or (key == "id" and not metadata[key]):
                    metadata[key] = default_val

            try:
                metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
                if metadata.get("embedding_provider") == "Unknown":
                    metadata["embedding_provider"] = KBAnalysisHelper._detect_embedding_provider(kb_path)
                if metadata.get("embedding_model") == "Unknown":
                    metadata["embedding_model"] = KBAnalysisHelper._detect_embedding_model(kb_path)

                metadata_file.write_text(json.dumps(metadata, indent=2))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
                logger.debug(f"Metadata backfill failed for {kb_path}: {e}")

        return metadata

    @staticmethod
    def update_text_metrics(kb_path: Path, metadata: dict, chroma: Chroma | None = None) -> None:
        """Update text metrics (chunks, words, characters) for a knowledge base."""
        try:
            if chroma is None:
                client = KBStorageHelper.get_fresh_chroma_client(kb_path)
                chroma = Chroma(client=client, collection_name=kb_path.name)

            collection = chroma._collection  # noqa: SLF001
            metadata["chunks"] = collection.count()

            if metadata["chunks"] > 0:
                total_words = 0
                total_characters = 0
                # Use a robust batch size to avoid SQLite limits and memory pressure
                batch_size = 5000

                for offset in range(0, metadata["chunks"], batch_size):
                    results = collection.get(
                        include=["documents"],
                        limit=batch_size,
                        offset=offset,
                    )
                    if not results["documents"]:
                        break

                    # Chroma collections always return the text content within the 'documents' field
                    source_chunks = pd.DataFrame({"document": results["documents"]})
                    words, characters = KBAnalysisHelper._calculate_text_metrics(source_chunks, ["document"])
                    total_words += words
                    total_characters += characters

                metadata["words"] = total_words
                metadata["characters"] = total_characters
                metadata["avg_chunk_size"] = (
                    round(total_characters / metadata["chunks"], 1) if metadata["chunks"] > 0 else 0.0
                )
        except (OSError, ValueError, TypeError, json.JSONDecodeError, chromadb.errors.ChromaError) as e:
            logger.debug(f"Metrics update failed for {kb_path.name}: {e}")

    @staticmethod
    def _detect_embedding_provider(kb_path: Path) -> str:
        """Internal helper to detect the embedding provider."""
        provider_patterns = {
            "OpenAI": ["openai", "text-embedding-ada", "text-embedding-3"],
            "Azure OpenAI": ["azure"],
            "HuggingFace": ["sentence-transformers", "huggingface", "bert-"],
            "Cohere": ["cohere", "embed-english", "embed-multilingual"],
            "Google": ["palm", "gecko", "google"],
            "Ollama": ["ollama"],
            "Chroma": ["chroma"],
        }

        for config_file in kb_path.glob("*.json"):
            try:
                with config_file.open("r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    if not isinstance(config_data, dict):
                        continue

                    config_str = json.dumps(config_data).lower()
                    provider_fields = ["embedding_provider", "provider", "embedding_model_provider"]
                    for field in provider_fields:
                        if field in config_data:
                            provider_value = str(config_data[field]).lower()
                            for provider, patterns in provider_patterns.items():
                                if any(pattern in provider_value for pattern in patterns):
                                    return provider
                            if provider_value and provider_value != "unknown":
                                return provider_value.title()

                    for provider, patterns in provider_patterns.items():
                        if any(pattern in config_str for pattern in patterns):
                            return provider

            except (OSError, json.JSONDecodeError):
                logger.exception("Error reading config file '%s'", config_file)
                continue

        if (kb_path / "chroma").exists():
            return "Chroma"
        if (kb_path / "vectors.npy").exists():
            return "Local"

        return "Unknown"

    @staticmethod
    def _detect_embedding_model(kb_path: Path) -> str:
        """Internal helper to detect the embedding model."""
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            try:
                with metadata_file.open("r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    if isinstance(metadata, dict) and "embedding_model" in metadata:
                        model_value = str(metadata.get("embedding_model", "unknown"))
                        if model_value and model_value.lower() != "unknown":
                            return model_value
            except (OSError, json.JSONDecodeError):
                logger.exception("Error reading embedding metadata file '%s'", metadata_file)

        for config_file in kb_path.glob("*.json"):
            if config_file.name == "embedding_metadata.json":
                continue

            try:
                with config_file.open("r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    if not isinstance(config_data, dict):
                        continue

                    model_fields = ["embedding_model", "model", "embedding_model_name", "model_name"]
                    for field in model_fields:
                        if field in config_data:
                            model_value = str(config_data[field])
                            if model_value and model_value.lower() != "unknown":
                                return model_value

                    if "openai" in json.dumps(config_data).lower():
                        openai_models = ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"]
                        config_str = json.dumps(config_data).lower()
                        for model in openai_models:
                            if model in config_str:
                                return model

                    if "model" in config_data:
                        model_name = str(config_data["model"])
                        hf_patterns = ["sentence-transformers", "all-MiniLM", "all-mpnet", "multi-qa"]
                        if any(pattern in model_name for pattern in hf_patterns):
                            return model_name

            except (OSError, json.JSONDecodeError):
                logger.exception("Error reading config file '%s'", config_file)
                continue

        return "Unknown"

    @staticmethod
    def _calculate_text_metrics(df: pd.DataFrame, text_columns: list[str]) -> tuple[int, int]:
        """Internal helper to calculate total words and characters."""
        total_words = 0
        total_characters = 0

        for col in text_columns:
            if col not in df.columns:
                continue

            text_series = df[col].astype(str).fillna("")
            total_characters += int(text_series.str.len().sum())
            total_words += int(text_series.str.split().str.len().sum())

        return total_words, total_characters


class KBIngestionHelper:
    """Helper class for Knowledge Base ingestion processes."""

    @staticmethod
    async def perform_ingestion(
        kb_name: str,
        kb_path: Path,
        files_data: list[tuple[str, bytes]],
        chunk_size: int,
        chunk_overlap: int,
        separator: str,
        source_name: str,
        current_user: CurrentActiveUser,
        embedding_provider: str,
        embedding_model: str,
        task_job_id: uuid.UUID,
        job_service: JobService,
    ) -> dict[str, object]:
        """Orchestrate the ingestion of files into a knowledge base."""
        try:
            processed_files = []
            total_chunks_created = 0

            splitter_kwargs: dict = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
            if separator:
                resolved_separator = separator.replace("\\n", "\n")
                splitter_kwargs["separators"] = [resolved_separator]
            text_splitter = RecursiveCharacterTextSplitter(**splitter_kwargs)

            embeddings = await KBIngestionHelper._build_embeddings(embedding_provider, embedding_model, current_user)

            client = KBStorageHelper.get_fresh_chroma_client(kb_path)
            chroma = Chroma(
                client=client,
                embedding_function=embeddings,
                collection_name=kb_name,
            )

            job_id_str = str(task_job_id)
            for file_name, file_content in files_data:
                await logger.ainfo("Starting ingestion of %s for %s", file_name, kb_name)
                content = extract_text_from_bytes(file_name, file_content)
                if not content.strip():
                    continue

                chunks = text_splitter.split_text(content)
                for i in range(0, len(chunks), INGESTION_BATCH_SIZE):
                    if await KBIngestionHelper._is_job_cancelled(job_service, task_job_id):
                        raise IngestionCancelledError

                    batch = chunks[i : i + INGESTION_BATCH_SIZE]
                    docs = [
                        Document(
                            page_content=c,
                            metadata={
                                "source": source_name or file_name,
                                "file_name": file_name,
                                "chunk_index": i + j,
                                "total_chunks": len(chunks),
                                "ingested_at": datetime.now(timezone.utc).isoformat(),
                                "job_id": job_id_str,
                            },
                        )
                        for j, c in enumerate(batch)
                    ]

                    for attempt in range(MAX_RETRY_ATTEMPTS):
                        if await KBIngestionHelper._is_job_cancelled(job_service, task_job_id):
                            raise IngestionCancelledError
                        try:
                            await chroma.aadd_documents(docs)
                            break
                        except Exception as e:
                            if attempt == MAX_RETRY_ATTEMPTS - 1:
                                raise
                            wait = (attempt + 1) * EXPONENTIAL_BACKOFF_MULTIPLIER
                            await logger.awarning("Write failed, retrying in %ds: %s", wait, e)
                            await asyncio.sleep(wait)

                    await asyncio.sleep(0.01)

                total_chunks_created += len(chunks)
                processed_files.append(file_name)

            metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
            KBAnalysisHelper.update_text_metrics(kb_path, metadata, chroma=chroma)
            metadata["size"] = KBStorageHelper.get_directory_size(kb_path)
            metadata["chunk_size"] = chunk_size
            metadata["chunk_overlap"] = chunk_overlap
            metadata["separator"] = separator or None
            metadata_path = kb_path / "embedding_metadata.json"
            new_source_types = list({f.rsplit(".", 1)[-1].lower() for f in processed_files if "." in f})
            existing_source_types = metadata.get("source_types", [])
            metadata["source_types"] = list(set(existing_source_types + new_source_types))
            metadata_path.write_text(json.dumps(metadata, indent=2))
            await logger.ainfo(f"Completed ingestion for {kb_name}")

            return {
                "message": f"Successfully ingested {len(processed_files)} file(s)",
                "files_processed": len(processed_files),
                "chunks_created": total_chunks_created,
            }

        except IngestionCancelledError:
            await logger.awarning(f"Ingestion job {task_job_id} was cancelled. Cleaning up partial data...")
            await KBIngestionHelper.cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
            return {"message": "Job cancelled"}
        except Exception as e:
            await logger.aerror(f"Error in background ingestion: {e!s}. Initiating rollback...")
            await KBIngestionHelper.cleanup_chroma_chunks_by_job(task_job_id, kb_path, kb_name)
            raise
        finally:
            chroma = None
            gc.collect()

    @staticmethod
    async def cleanup_chroma_chunks_by_job(
        job_id: uuid.UUID,
        kb_path: Path,
        kb_name: str,
    ) -> None:
        """Clean up ChromaDB chunks associated with a specific job ID."""
        try:
            client = KBStorageHelper.get_fresh_chroma_client(kb_path)
            chroma = Chroma(
                client=client,
                collection_name=kb_name,
            )
            await chroma.adelete(where={"job_id": str(job_id)})
            await logger.ainfo(f"Cleaned up chunks for job {job_id} in knowledge base '{kb_name}'")
        except (OSError, ValueError, TypeError, chromadb.errors.ChromaError) as cleanup_error:
            await logger.aerror(f"Failed to clean up chunks for job {job_id}: {cleanup_error}")
        finally:
            chroma = None
            gc.collect()

    @staticmethod
    async def _is_job_cancelled(job_service: JobService, job_id: uuid.UUID) -> bool:
        """Internal helper to check if a job has been cancelled."""
        job = await job_service.get_job_by_job_id(job_id)
        return job is not None and job.status == JobStatus.CANCELLED

    @staticmethod
    async def _build_embeddings(provider: str, model: str, current_user):
        """Internal helper to build embeddings object."""
        options = get_embedding_model_options(user_id=current_user.id)
        selected_option = next((o for o in options if o["provider"] == provider and o["name"] == model), None)

        if not selected_option:
            all_options = get_embedding_model_options()
            selected_option = next((o for o in all_options if o["provider"] == provider and o["name"] == model), None)

            if not selected_option:
                msg = f"Embedding model '{model}' for provider '{provider}' not found."
                raise ValueError(msg)

        embedding_model = EmbeddingModelComponent(model=[selected_option], _user_id=current_user.id)
        embeddings_with_models = embedding_model.build_embeddings()
        return embeddings_with_models.embeddings


# Additional utility function for Windows-specific deletion
def force_delete_knowledge_base_windows(kb_path: Path, kb_name: str, max_retries: int = 5) -> bool:
    """
    Force delete a knowledge base on Windows with aggressive cleanup.
    
    Args:
        kb_path: Path to the knowledge base directory
        kb_name: Name of the knowledge base
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if successful, False otherwise
    """
    if not kb_path.exists():
        return True
    
    # First, ensure all connections are closed
    connection_manager = ChromaConnectionManager.get_instance()
    connection_manager.close_all_connections()
    
    for attempt in range(max_retries):
        try:
            # Close any remaining connections
            KBStorageHelper.teardown_storage(kb_path, kb_name)
            
            # Force garbage collection
            gc.collect()
            
            # Wait with exponential backoff
            if attempt > 0:
                time.sleep(0.5 * (2 ** attempt))
            
            # Windows specific: Try to remove lock files first
            if platform.system() == "Windows":
                # Remove SQLite auxiliary files
                for pattern in ["*.sqlite3-wal", "*.sqlite3-shm", "*.sqlite3-journal"]:
                    for lock_file in kb_path.glob(pattern):
                        try:
                            lock_file.unlink()
                        except:
                            pass
                
                # Try to truncate SQLite files
                for sqlite_file in kb_path.glob("*.sqlite3"):
                    try:
                        with open(sqlite_file, 'r+b') as f:
                            f.truncate(0)
                    except:
                        pass
            
            # Try to remove the directory
            shutil.rmtree(kb_path, ignore_errors=False)
            
            # Verify deletion
            if not kb_path.exists():
                logger.info(f"Successfully deleted knowledge base {kb_name}")
                return True
                
        except OSError as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to delete {kb_name} after {max_retries} attempts: {e}")
            else:
                logger.debug(f"Deletion attempt {attempt + 1} failed for {kb_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error deleting {kb_name}: {e}")
    
    # Last resort on Windows: rename for later cleanup
    if platform.system() == "Windows" and kb_path.exists():
        try:
            temp_path = kb_path.with_name(f"{kb_name}_deleted_{int(time.time())}")
            kb_path.rename(temp_path)
            logger.info(f"Renamed {kb_name} to {temp_path.name} for later cleanup")
            return True
        except Exception as e:
            logger.error(f"Failed to rename {kb_name}: {e}")
    
    return False
