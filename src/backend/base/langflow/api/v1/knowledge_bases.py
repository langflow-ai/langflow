import json
import os
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases")

KNOWLEDGE_BASES_DIR = "~/.langflow/knowledge_bases"


class KnowledgeBaseInfo(BaseModel):
    id: str
    name: str
    embedding_provider: Optional[str] = "Unknown"
    size: int = 0
    words: int = 0
    characters: int = 0
    chunks: int = 0
    avg_chunk_size: float = 0.0


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
                        
        except Exception:
            continue
    
    # Fallback to directory structure
    if (kb_path / "chroma").exists():
        return "Chroma"
    elif (kb_path / "vectors.npy").exists():
        return "Local"
    
    return "Unknown"


def get_text_columns(df: pd.DataFrame, schema_data: list = None) -> list[str]:
    """Get the text columns to analyze for word/character counts."""
    # First try schema-defined text columns
    if schema_data:
        text_columns = [
            col["column_name"] for col in schema_data 
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
    metadata = {
        "chunks": 0,
        "words": 0,
        "characters": 0,
        "avg_chunk_size": 0.0,
        "embedding_provider": "Unknown",
    }
    
    try:
        # Detect embedding provider
        metadata["embedding_provider"] = detect_embedding_provider(kb_path)
        
        # Read schema for text column information
        schema_data = None
        schema_file = kb_path / "schema.json"
        if schema_file.exists():
            try:
                with schema_file.open("r", encoding="utf-8") as f:
                    schema_data = json.load(f)
                    if not isinstance(schema_data, list):
                        schema_data = None
            except Exception:
                pass
        
        # Process source.parquet for text metrics
        source_file = kb_path / "source.parquet"
        if source_file.exists():
            try:
                df = pd.read_parquet(source_file)
                metadata["chunks"] = len(df)
                
                # Get text columns and calculate metrics
                text_columns = get_text_columns(df, schema_data)
                if text_columns:
                    words, characters = calculate_text_metrics(df, text_columns)
                    metadata["words"] = words
                    metadata["characters"] = characters
                    
                    # Calculate average chunk size
                    if metadata["chunks"] > 0:
                        metadata["avg_chunk_size"] = round(characters / metadata["chunks"], 1)
                        
            except Exception:
                pass
    
    except Exception:
        pass
    
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
                    size=size,
                    words=metadata["words"],
                    characters=metadata["characters"],
                    chunks=metadata["chunks"],
                    avg_chunk_size=metadata["avg_chunk_size"],
                )
                
                knowledge_bases.append(kb_info)
                
            except Exception as e:
                # Skip directories that can't be read
                continue
        
        # Sort by name alphabetically
        knowledge_bases.sort(key=lambda x: x.name)
        
        return knowledge_bases
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error listing knowledge bases: {str(e)}"
        ) from e


@router.get("/{kb_name}", status_code=HTTPStatus.OK)
async def get_knowledge_base(kb_name: str) -> KnowledgeBaseInfo:
    """Get detailed information about a specific knowledge base."""
    try:
        kb_root_path = get_kb_root_path()
        kb_path = kb_root_path / kb_name
        
        if not kb_path.exists() or not kb_path.is_dir():
            raise HTTPException(
                status_code=404, 
                detail=f"Knowledge base '{kb_name}' not found"
            )
        
        # Get size of the directory
        size = get_directory_size(kb_path)
        
        # Get metadata from KB files
        metadata = get_kb_metadata(kb_path)
        
        return KnowledgeBaseInfo(
            id=kb_name,
            name=kb_name.replace("_", " ").replace("-", " ").title(),
            embedding_provider=metadata["embedding_provider"],
            size=size,
            words=metadata["words"],
            characters=metadata["characters"],
            chunks=metadata["chunks"],
            avg_chunk_size=metadata["avg_chunk_size"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error getting knowledge base '{kb_name}': {str(e)}"
        ) from e 