"""Azure Document Intelligence Component - Form recognition and document processing with user-specific LRU caching."""

import asyncio
import builtins
import concurrent.futures
import hashlib
import mimetypes
import os
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Tuple
from urllib.parse import unquote, urlparse

import aiohttp
import requests
from langflow.base.data import BaseFileComponent
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, Output
from langflow.schema.data import Data
from loguru import logger


class LRUCache:
    """LRU Cache with size limit and automatic eviction."""
    
    def __init__(self, max_size: int = 100):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Tuple[Data, str] | None:
        """Get item from cache and move to end (most recently used)."""
        if key not in self.cache:
            self.misses += 1
            return None
        
        self.cache.move_to_end(key)
        self.hits += 1
        return self.cache[key]
    
    def put(self, key: str, value: Tuple[Data, str]):
        """Put item in cache, evict LRU if needed."""
        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = value
        else:
            self.cache[key] = value
            self.cache.move_to_end(key)
            
            if len(self.cache) > self.max_size:
                evicted_key = next(iter(self.cache))
                del self.cache[evicted_key]
                logger.info(f"🗑️ LRU evicted oldest entry (cache: {len(self.cache)}/{self.max_size})")
    
    def clear(self):
        """Clear the cache."""
        size = len(self.cache)
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        return size
    
    def clear_user(self, user_id: str) -> int:
        """Clear cache entries for a specific user."""
        user_prefix = f"user_{user_id}_"
        keys_to_delete = [k for k in self.cache.keys() if k.startswith(user_prefix)]
        for key in keys_to_delete:
            del self.cache[key]
        return len(keys_to_delete)
    
    def __len__(self):
        return len(self.cache)
    
    def get_stats(self, user_id: str = None) -> dict:
        """Get cache statistics, optionally filtered by user."""
        if user_id:
            user_prefix = f"user_{user_id}_"
            user_entries = sum(1 for k in self.cache.keys() if k.startswith(user_prefix))
            return {
                "user_entries": user_entries,
                "total_size": len(self.cache),
                "max_size": self.max_size,
            }
        
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }


# Initialize cache in builtins for persistence across module reloads
if not hasattr(builtins, '_azure_doc_intel_cache'):
    builtins._azure_doc_intel_cache = None

# Initialize global LRU cache using builtins for persistence
cache_instance = getattr(builtins, '_azure_doc_intel_cache', None)
if cache_instance is None:
    builtins._azure_doc_intel_cache = LRUCache(max_size=100)
    logger.info(f"🔧 Created NEW global LRU cache in builtins (max: 100 files)")
else:
    try:
        cache_stats = getattr(builtins, '_azure_doc_intel_cache', None)
        if cache_stats:
            cache_stats = cache_stats.get_stats()
            logger.info(f"🔄 Reusing existing cache from builtins: {cache_stats}")
    except Exception:
        logger.info(f"🔄 Reusing existing cache from builtins")


class AzureDocumentIntelligenceComponent(BaseFileComponent):
    """Component for Azure Document Intelligence with user-specific LRU caching."""

    display_name: str = "Azure Document Intelligence"
    description: str = "Process documents using Azure Document Intelligence with user-specific LRU cache"
    documentation: str = "https://docs.microsoft.com/en-us/azure/applied-ai-services/form-recognizer/"
    icon: str = "Azure"
    name: str = "AzureDocumentIntelligence"
    category: str = "models"
    priority: int = 3

    VALID_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif"]

    inputs = [
        HandleInput(
            name="url",
            display_name="URL",
            info="URL to the document to process",
            input_types=["str", "Data", "Message", "list"],
            required=False,
        ),
        next(input for input in BaseFileComponent._base_inputs if input.name == "file_path"),
        next(input for input in BaseFileComponent._base_inputs if input.name == "silent_errors"),
        next(input for input in BaseFileComponent._base_inputs if input.name == "delete_server_file_after_processing"),
        next(input for input in BaseFileComponent._base_inputs if input.name == "ignore_unsupported_extensions"),
        next(input for input in BaseFileComponent._base_inputs if input.name == "ignore_unspecified_files"),
        DropdownInput(
            name="model_type",
            display_name="Model Type",
            options=["prebuilt-document", "prebuilt-read", "prebuilt-layout"],
            value="prebuilt-document",
            info="Choose the Form Recognizer model to use",
        ),
        BoolInput(
            name="extract_tables",
            display_name="Extract Tables",
            value=True,
            info="Extract and format tables from the document",
        ),
        BoolInput(
            name="include_confidence",
            display_name="Include Confidence Scores",
            value=False,
            advanced=True,
            info="Include confidence scores in the extracted text",
        ),
        BoolInput(
            name="generate_hash",
            display_name="Generate File Hash",
            value=True,
            advanced=True,
            info="Generate MD5 hash of file content for deduplication",
        ),
        BoolInput(
            name="use_multithreading",
            display_name="Use Concurrent Processing",
            value=True,
            info="Enable concurrent processing of multiple files",
        ),
        IntInput(
            name="concurrency_multithreading",
            display_name="Processing Concurrency",
            advanced=True,
            info="Number of files to process concurrently",
            value=2,
        ),
        BoolInput(
            name="enable_cache",
            display_name="Enable User Cache",
            value=True,
            info="Cache processing results per user - isolated from other users",
        ),
        IntInput(
            name="cache_max_size",
            display_name="Cache Max Size",
            value=5,
            advanced=True,
            info="Maximum number of files to keep in cache (LRU eviction when full)",
        ),
        BoolInput(
            name="clear_cache",
            display_name="Clear My Cache",
            value=False,
            advanced=True,
            info="Clear only YOUR cached documents (does not affect other users)",
        ),
    ]

    outputs = [
        Output(display_name="Structured Data", name="structured_data", method="load_files"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.temp_dir = tempfile.mkdtemp()
        self._downloaded_files = {}
        self._text_content = ""

    def get_text_content(self) -> str:
        """Return the concatenated text content from all processed pages."""
        return self._text_content

    def _get_user_id(self) -> str:
        """Get the current user ID from the graph/session context."""
        try:
            if hasattr(self, 'vertex') and self.vertex:
                if hasattr(self.vertex, 'graph') and self.vertex.graph:
                    graph = self.vertex.graph
                    if hasattr(graph, 'user_id') and graph.user_id:
                        return str(graph.user_id)
                    if hasattr(graph, '_user_id') and graph._user_id:
                        return str(graph._user_id)
                    if hasattr(graph, 'metadata') and isinstance(graph.metadata, dict):
                        user_id = graph.metadata.get('user_id')
                        if user_id:
                            return str(user_id)
            if hasattr(self, '_session_id'):
                return f"session_{self._session_id}"
            return "default_user"
        except Exception:
            return "default_user"

    @classmethod
    def get_lru_cache(cls) -> LRUCache:
        """Get the global LRU cache."""
        cache = getattr(builtins, '_azure_doc_intel_cache', None)
        if cache is None:
            cache = LRUCache(max_size=100)
            builtins._azure_doc_intel_cache = cache
        return cache

    def clear_user_cache(self):
        """Clear cache for the current user only."""
        user_id = self._get_user_id()
        lru = self.get_lru_cache()
        count = lru.clear_user(user_id)
        logger.warning(f"🗑️ Cleared {count} cache entries for user {user_id}")

    @classmethod
    def clear_global_cache(cls):
        """Clear the entire global LRU cache (all users)."""
        lru = cls.get_lru_cache()
        size = lru.clear()
        logger.warning(f"🗑️ Global LRU cache cleared ({size} files)")

    @classmethod
    def get_cache_stats(cls, user_id: str = None) -> dict:
        """Get cache statistics."""
        return cls.get_lru_cache().get_stats(user_id)

    def _generate_cache_key(self, file_path: str, file_hash: str = None) -> str:
        """Generate a user-specific cache key based on file hash or file path."""
        user_id = self._get_user_id()
        
        if file_hash:
            cache_components = [
                user_id,
                file_hash,
                self.model_type,
                str(self.extract_tables),
                str(self.include_confidence),
            ]
        else:
            cache_components = [
                user_id,
                file_path,
                self.model_type,
                str(self.extract_tables),
                str(self.include_confidence),
            ]
        
        cache_string = "|".join(cache_components)
        prefix = "hash" if file_hash else "path"
        return f"user_{user_id}_{prefix}_{hashlib.md5(cache_string.encode()).hexdigest()}"

    def _generate_file_hash(self, file_path: str) -> str | None:
        """Generate MD5 hash of file content."""
        try:
            md5_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    md5_hash.update(chunk)
            hash_value = md5_hash.hexdigest()
            logger.debug(f"Generated hash for {Path(file_path).name}: {hash_value}")
            return hash_value
        except Exception as e:
            logger.error(f"Error generating hash for {file_path}: {e}")
            return None

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL or generate a default one."""
        try:
            parsed_url = urlparse(url)
            path = unquote(parsed_url.path)
            filename = os.path.basename(path)
            if filename and "." in filename:
                return filename
            response = requests.head(url, allow_redirects=True)
            if "content-disposition" in response.headers:
                content_disp = response.headers["content-disposition"]
                if "filename=" in content_disp:
                    return content_disp.split("filename=")[1].strip("\"'")
            if "content-type" in response.headers:
                ext = mimetypes.guess_extension(response.headers["content-type"])
                if ext:
                    return f"downloaded{ext}"
            return "downloaded.pdf"
        except Exception as e:
            logger.error(f"Error extracting filename from URL: {e!s}")
            return "downloaded.pdf"

    async def _download_file_from_url(self, url: str) -> str | None:
        """Download a file from a URL."""
        try:
            filename = self._extract_filename_from_url(url)
            local_path = os.path.join(self.temp_dir, filename)
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    with open(local_path, "wb") as f:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
            self._downloaded_files[url] = local_path
            logger.info(f"Successfully downloaded file to {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Error downloading file from URL: {e!s}")
            if not self.silent_errors:
                raise
            return None

    def _extract_url_from_input(self, input_data) -> str | None:
        """Extract URL string from various input types."""
        if isinstance(input_data, list):
            if input_data and isinstance(input_data[0], Data):
                return input_data[0].data.get("file_path")
            return None
        if isinstance(input_data, str):
            return input_data
        elif isinstance(input_data, Data):
            return input_data.data.get("file_path") or input_data.data.get("url") or input_data.text
        elif hasattr(input_data, "text"):
            return input_data.text
        elif hasattr(input_data, "data"):
            return input_data.data.get("file_path") or input_data.data.get("url") or input_data.text
        return None

    def _validate_and_resolve_paths(self) -> list[BaseFileComponent.BaseFile]:
        """Handle URLs and local paths."""
        resolved_files = []
        user_id = self._get_user_id()
        
        lru = self.get_lru_cache()
        if hasattr(self, 'cache_max_size') and lru.max_size != self.cache_max_size:
            lru.max_size = self.cache_max_size
            logger.info(f"📏 Updated cache max size to {self.cache_max_size}")
        
        if self.clear_cache:
            self.clear_user_cache()
        
        stats = self.get_cache_stats(user_id)
        logger.info(f"📊 User {user_id} cache: {stats}")

        # Handle URL input if provided
        if hasattr(self, "url") and self.url:
            try:
                url = self._extract_url_from_input(self.url)
                if url:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        local_path = loop.run_until_complete(self._download_file_from_url(url))
                    finally:
                        loop.close()
                    if local_path:
                        new_data = Data(data={
                            self.SERVER_FILE_PATH_FIELDNAME: local_path,
                            "original_url": url,
                        })
                        resolved_files.append(BaseFileComponent.BaseFile(
                            new_data, Path(local_path),
                            delete_after_processing=self.delete_server_file_after_processing,
                        ))
            except Exception as e:
                logger.error(f"Error processing URL {url}: {e!s}")
                if not self.silent_errors:
                    raise

        # Handle file_path input
        file_path = self._file_path_as_list()
        for obj in file_path:
            server_file_path = obj.data.get(self.SERVER_FILE_PATH_FIELDNAME)
            if not server_file_path:
                if not self.ignore_unspecified_files:
                    msg = f"Data object missing '{self.SERVER_FILE_PATH_FIELDNAME}' property."
                    if not self.silent_errors:
                        raise ValueError(msg)
                continue
            try:
                if isinstance(server_file_path, str) and server_file_path.startswith(("http://", "https://")):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        local_path = loop.run_until_complete(self._download_file_from_url(server_file_path))
                    finally:
                        loop.close()
                    if not local_path:
                        continue
                    new_data = Data(data={
                        self.SERVER_FILE_PATH_FIELDNAME: local_path,
                        "original_url": server_file_path,
                    })
                    resolved_files.append(BaseFileComponent.BaseFile(
                        new_data, Path(local_path),
                        delete_after_processing=self.delete_server_file_after_processing,
                    ))
                else:
                    resolved_path = Path(self.resolve_path(str(server_file_path)))
                    if not resolved_path.exists():
                        msg = f"File not found: {server_file_path}"
                        if not self.silent_errors:
                            raise ValueError(msg)
                        continue
                    resolved_files.append(BaseFileComponent.BaseFile(
                        obj, resolved_path,
                        delete_after_processing=self.delete_server_file_after_processing,
                    ))
            except Exception as e:
                logger.error(f"Error processing path {server_file_path}: {e!s}")
                if not self.silent_errors:
                    raise
                continue
        return resolved_files

    def _get_original_url_from_basefile(self, base_file) -> str | None:
        """Extract original_url from BaseFile object."""
        try:
            if hasattr(base_file, 'data_object'):
                return base_file.data_object.data.get("original_url")
            elif hasattr(base_file, 'data'):
                if isinstance(base_file.data, Data):
                    return base_file.data.data.get("original_url")
                elif isinstance(base_file.data, dict):
                    return base_file.data.get("original_url")
            elif hasattr(base_file, '__getitem__'):
                try:
                    data_obj = base_file[0]
                    if isinstance(data_obj, Data):
                        return data_obj.data.get("original_url")
                except (IndexError, TypeError):
                    pass
        except Exception as e:
            logger.debug(f"Could not extract original_url: {e}")
        return None

    async def process_file(
        self, file_path: str, original_url: str = None, *, silent_errors: bool = False
    ) -> Tuple[Data, str]:
        """Process a single file using the OCR service with user-specific LRU caching."""
        try:
            user_id = self._get_user_id()
            
            file_hash = None
            if self.generate_hash:
                file_hash = self._generate_file_hash(file_path)
            cache_key = self._generate_cache_key(file_path, file_hash)
            
            if self.enable_cache:
                lru = self.get_lru_cache()
                cached_result = lru.get(cache_key)
                if cached_result:
                    logger.info(f"✓ USER CACHE HIT for {Path(file_path).name} (user: {user_id})")
                    cached_data, cached_text = cached_result
                    
                    updated_data_dict = cached_data.data.copy()
                    updated_data_dict[self.SERVER_FILE_PATH_FIELDNAME] = str(file_path)
                    
                    if "metadata" in updated_data_dict:
                        updated_data_dict["metadata"] = updated_data_dict["metadata"].copy()
                        updated_data_dict["metadata"]["file_name"] = Path(file_path).name
                        if original_url:
                            updated_data_dict["metadata"]["original_url"] = original_url
                    
                    if original_url:
                        updated_data_dict["original_url"] = original_url
                    
                    updated_data = Data(text=cached_text, data=updated_data_dict)
                    return (updated_data, cached_text)
            
            logger.info(f"⚡ Processing file (cache miss): {Path(file_path).name} (user: {user_id})")
            
            from langflow.services.deps import get_document_intelligence_service
            ocr_service = get_document_intelligence_service()

            with open(file_path, "rb") as file:
                file_content = file.read()

            extracted_content, plain_text, document_uuid = await ocr_service.process_document(
                file_content=file_content,
                model_type=self.model_type,
                include_confidence=self.include_confidence,
                extract_tables=self.extract_tables,
                file_hash=file_hash
            )

            data_dict = {
                self.SERVER_FILE_PATH_FIELDNAME: str(file_path),
                "result": extracted_content,
                "document_uuid": document_uuid,
                "cache_key": cache_key,
            }
            
            if file_hash:
                data_dict["file_hash"] = file_hash
                data_dict["hash_type"] = "file_content"
                data_dict["metadata"] = {
                    "file_hash": file_hash,
                    "hash_type": "file_content",
                    "file_name": Path(file_path).name,
                    "cache_key": cache_key,
                    "user_id": user_id,
                }
                if original_url:
                    data_dict["original_url"] = original_url
                    data_dict["metadata"]["original_url"] = original_url
                    data_dict["metadata"]["source_type"] = "url"
                else:
                    data_dict["metadata"]["source_type"] = "local"
                    
                logger.info(f"Added hash to OCR output: {file_hash}")

            structured_data = Data(text=plain_text, data=data_dict)
            result = (structured_data, plain_text)
            
            if self.enable_cache:
                lru.put(cache_key, result)
                stats = lru.get_stats(user_id)
                logger.info(f"💾 Saved to user cache (user: {user_id}): {stats}")

            return result

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e!s}")
            if not silent_errors:
                raise
            return None, ""

    def process_files(
        self, file_list: list[BaseFileComponent.BaseFile]
    ) -> list[BaseFileComponent.BaseFile]:
        """Process multiple files with concurrent processing and user-specific LRU caching."""
        if not file_list:
            logger.warning("No files to process - returning empty results")
            return []

        concurrency = 1 if not self.use_multithreading else max(1, self.concurrency_multithreading)
        file_count = len(file_list)
        user_id = self._get_user_id()

        logger.info(f"Processing {file_count} files with concurrency: {concurrency} (user: {user_id})")

        all_plain_text = []
        processed_data = []

        if concurrency > 1 and file_count > 1:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                    future_to_file = {
                        executor.submit(
                            lambda f: loop.run_until_complete(
                                self.process_file(
                                    str(f.path),
                                    original_url=self._get_original_url_from_basefile(f),
                                    silent_errors=self.silent_errors
                                )
                            ),
                            file,
                        ): file
                        for file in file_list
                    }
                    for future in concurrent.futures.as_completed(future_to_file):
                        try:
                            structured_data, plain_text = future.result()
                            processed_data.append(structured_data)
                            all_plain_text.append(plain_text)
                        except Exception as e:
                            logger.error(f"Error in concurrent processing: {e!s}")
                            if not self.silent_errors:
                                raise
                            processed_data.append(None)
                            all_plain_text.append("")
            finally:
                loop.close()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                for file in file_list:
                    try:
                        original_url = self._get_original_url_from_basefile(file)
                        structured_data, plain_text = loop.run_until_complete(
                            self.process_file(
                                str(file.path),
                                original_url=original_url,
                                silent_errors=self.silent_errors
                            )
                        )
                        processed_data.append(structured_data)
                        all_plain_text.append(plain_text)
                    except Exception as e:
                        logger.error(f"Error processing file {file.path}: {e!s}")
                        if not self.silent_errors:
                            raise
                        processed_data.append(None)
                        all_plain_text.append("")
            finally:
                loop.close()

        self._text_content = "\n\n=== NEW DOCUMENT ===\n\n".join(all_plain_text)
        
        stats = self.get_cache_stats(user_id)
        logger.info(f"✅ Processing complete (user: {user_id}). Cache stats: {stats}")

        return self.rollup_data(file_list, processed_data)

    def __del__(self):
        """Cleanup temporary files and directory."""
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                for file_path in self._downloaded_files.values():
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                os.rmdir(self.temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e!s}")