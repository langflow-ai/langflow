import json
import logging
import re

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from pymongo.collection import Collection

from lfx.custom import Component
from lfx.field_typing import Tool
from lfx.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema import Data

logger = logging.getLogger(__name__)


class MongoDBQueryComponent(Component):
    display_name = "MongoDB NoSQL"
    description = "MongoDB NoSQL Component with CRUD operations"
    name = "MongoDBNoSQL"
    icon = "MongoDB"
    OPERATIONS = ["query", "insert", "update", "delete", "replace"]
    INSERT_MODES = ["append", "overwrite"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mongo_client = None

    inputs = [
        SecretStrInput(
            name="mongodb_nosql_uri",
            display_name="MongoDB NoSQL URI",
            info="MongoDB connection URI, e.g. mongodb://username:password@host:port",
            required=True,
        ),
        StrInput(name="db_name", display_name="Database Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=OPERATIONS,
            value=OPERATIONS[0],
            info="Select the operation to perform: query, insert, update, delete, or replace",
        ),
        MessageTextInput(
            name="search_query",
            display_name="Filter/Query (JSON)",
            info="Filter for query/update/delete/replace. Examples:\n"
            '• {"title": "The Great Train Robbery"}\n'
            "• {title:'The Great Train Robbery',runtime:11}\n"
            "• {} (empty for query all or insert)",
            value="{}",
            tool_mode=True,
        ),
        MessageTextInput(
            name="document_data",
            display_name="Document Data (JSON)",
            info="Data for insert/update/replace operations. Examples:\n"
            '• Insert: {"title":"New Movie","runtime":120}\n'
            '• Update: {"runtime":15} (updates only these fields)\n'
            '• Replace: {"title":"Movie","runtime":120} (replaces entire document)',
            value="{}",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit Results",
            info="Maximum number of documents to return (query operation only)",
            value=10,
        ),
        BoolInput(
            name="upsert",
            display_name="Upsert",
            value=False,
            info="For update/replace: if no document matches, insert a new one",
            advanced=True,
        ),
        BoolInput(
            name="update_many",
            display_name="Update/Delete Many",
            value=False,
            info="If True, affects all matching documents. If False, only first match.",
            advanced=True,
        ),
        MessageTextInput(
            name="ingest_data",
            display_name="Bulk Insert Data",
            info="List of documents for bulk insert (insert operation only)",
            is_list=True,
            required=False,
            advanced=True,
        ),
        DropdownInput(
            name="insert_mode",
            display_name="Insert Mode",
            options=INSERT_MODES,
            value=INSERT_MODES[0],
            info="Bulk insert mode: append (add to existing) or overwrite (clear collection first)",
            advanced=True,
        ),
        BoolInput(
            name="overwrite_confirmed",
            display_name="Confirm Collection Overwrite",
            value=False,
            info=(
                "REQUIRED for overwrite mode: explicitly confirm to delete all existing "
                "documents in the collection before inserting new ones. This is a safety "
                "measure to prevent accidental data loss."
            ),
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="query_mongodb"),
    ]

    class MongoDBQuerySchema(BaseModel):
        """Schema for MongoDB query tool."""

        filter: str | dict = Field(
            ...,
            description="MongoDB filter query as JSON string or dict. Examples: "
            '{"title": "Movie Name"} or {"year": {"$gt": 2020}} or {} for all documents.',
        )

    class MongoDBInsertSchema(BaseModel):
        """Schema for MongoDB insert tool."""

        document: str | dict = Field(
            ...,
            description='Document(s) to insert as JSON. Examples: {"title": "New Movie", "runtime": 120}',
        )

    class MongoDBUpdateSchema(BaseModel):
        """Schema for MongoDB update tool."""

        filter: str | dict = Field(
            ...,
            description="MongoDB filter to find documents to update. Examples: "
            '{"title": "Movie Name"} or {"session_id": "uuid-123456789"}',
        )
        update: str | dict = Field(
            ...,
            description=(
                'Data to update as JSON. Examples: {"runtime": 120} or {"$set": {"sinais_vitais.temperatura": 40}}'
            ),
        )

    class MongoDBReplaceSchema(BaseModel):
        """Schema for MongoDB replace tool."""

        filter: str | dict = Field(
            ...,
            description="MongoDB filter to find document to replace. Examples: "
            '{"title": "Movie Name"} or {"session_id": "uuid-123456789"}',
        )
        replacement: str | dict = Field(
            ...,
            description='New document to replace with as JSON. Examples: {"title": "Updated Movie", "runtime": 150}',
        )

    class MongoDBDeleteSchema(BaseModel):
        """Schema for MongoDB delete tool."""

        filter: str | dict = Field(
            ...,
            description="MongoDB filter to find documents to delete. Examples: "
            '{"title": "Movie Name"} or {"session_id": "uuid-123456789"}',
        )

    def parse_json(self, json_string: str) -> dict:
        """Parse JSON string to dict with support for relaxed JSON formats.

        Accepts both formats:
        - {"title": "value", "runtime": 11}  (standard JSON)
        - {title:'value',runtime:11}  (JavaScript-like)

        Carefully handles single quotes and apostrophes to avoid corruption
        of values containing apostrophes (e.g., "It's a movie").
        """
        if not json_string or json_string.strip() in ["{}", ""]:
            return {}

        try:
            # Try parsing as standard JSON first
            return json.loads(json_string)
        except json.JSONDecodeError:
            # Try to fix JavaScript-like format with careful quote handling
            try:
                fixed_json = json_string

                # Targeted single-quote replacement only at key/value boundaries
                # Replace opening single quotes (after { , or : with optional whitespace)
                fixed_json = re.sub(r"([{,:]\s*)'", r'\1"', fixed_json)

                # Replace closing single quotes (before } , or : with optional whitespace)
                fixed_json = re.sub(r"'(\s*[},:])", r'"\1', fixed_json)

                # Handle single quotes at end of input (before closing brace)
                fixed_json = re.sub(r"'(\s*})", r'"\1', fixed_json)

                # Add quotes around unquoted keys
                fixed_json = re.sub(r"(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', fixed_json)

                return json.loads(fixed_json)
            except json.JSONDecodeError as e:
                msg = f"Invalid JSON format: {e}\n\nExpected format:\n{{'key':'value'}}\nor\n{{\"key\":\"value\"}}"
                raise ValueError(msg) from e

    def get_collection(self) -> Collection:
        """Get MongoDB collection with cached connection.

        Caches the MongoClient on the instance to prevent connection leaks.
        The connection should be closed by calling close() when done.
        """
        try:
            from pymongo import MongoClient
        except ImportError as e:
            msg = "Please install pymongo to use MongoDB NoSQL"
            raise ImportError(msg) from e

        try:
            # Reuse cached client if available
            if self._mongo_client is None:
                self._mongo_client = MongoClient(self.mongodb_nosql_uri)
        except Exception as e:
            msg = f"Failed to connect to MongoDB NoSQL: {e}"
            raise ValueError(msg) from e
        else:
            return self._mongo_client[self.db_name][self.collection_name]

    def close(self):
        """Close the MongoDB connection and clear the cached client.

        Call this method when the component is done to properly close the connection
        and prevent resource leaks.
        """
        if self._mongo_client is not None:
            try:
                self._mongo_client.close()
                logger.info("MongoDB connection closed")
            except Exception:
                logger.exception("Error closing MongoDB connection")
            finally:
                self._mongo_client = None

    def __del__(self):
        """Cleanup: ensure connection is closed when component is garbage collected."""
        self.close()

    def convert_objectid_to_str(self, doc: dict) -> dict:
        """Recursively convert all ObjectId fields to strings for safe JSON serialization.

        Traverses nested dictionaries and lists to find and convert ObjectId instances,
        including nested structures within arrays and subdocuments.
        """
        from bson.objectid import ObjectId

        def convert_value(value):
            """Recursively convert ObjectId instances in any value."""
            if isinstance(value, ObjectId):
                return str(value)
            if isinstance(value, dict):
                # Recurse into dict values
                for key, val in value.items():
                    value[key] = convert_value(val)
                return value
            if isinstance(value, (list, tuple)):
                # Recurse into list/tuple elements
                converted = [convert_value(item) for item in value]
                # Preserve tuple type if input was tuple
                return tuple(converted) if isinstance(value, tuple) else converted
            # Return other types unchanged
            return value

        # Start recursive conversion on the document
        for key, value in doc.items():
            doc[key] = convert_value(value)
        return doc

    def _redact_sensitive(self, obj: dict | list) -> dict:
        """Extract safe metadata from object without exposing sensitive data.

        Returns only key names, types, and counts instead of actual values.
        """
        if isinstance(obj, dict):
            return {
                "keys": list(obj.keys()),
                "count": len(obj),
            }
        if isinstance(obj, list):
            return {"count": len(obj)}
        return {"type": type(obj).__name__}

    def query_operation(self, collection: Collection) -> list[Data]:
        """Execute query operation."""
        query_filter = self.parse_json(self.search_query)
        self.log(f"Executing query with filter: {self._redact_sensitive(query_filter)}")

        cursor = collection.find(query_filter).limit(self.limit)

        results = []
        for raw_doc in cursor:
            converted_doc = self.convert_objectid_to_str(raw_doc)
            results.append(Data(data=converted_doc))

        self.log(f"Found {len(results)} documents")
        return results

    def insert_operation(self, collection: Collection) -> list[Data]:
        """Execute insert operation."""
        documents = []

        # Check for bulk insert data
        if self.ingest_data:
            for _input in self.ingest_data:
                if isinstance(_input, Data):
                    doc_dict = _input.data if hasattr(_input, "data") else _input.__dict__
                    documents.append(doc_dict)
                elif isinstance(_input, dict):
                    documents.append(_input)

        # Check for single document data
        document_data = self.parse_json(self.document_data)
        if document_data:
            documents.append(document_data)

        if not documents:
            msg = "No documents to insert. Provide data in 'Document Data' or 'Bulk Insert Data'"
            raise ValueError(msg)

        # Handle insert mode
        if self.insert_mode == "overwrite":
            if not self.overwrite_confirmed:
                msg = (
                    "Overwrite mode requires explicit confirmation via 'Confirm Collection Overwrite' flag. "
                    "This prevents accidental deletion of all documents in the collection. "
                    "Please set 'Confirm Collection Overwrite' to True if you want to proceed."
                )
                raise ValueError(msg)

            # Warn before deleting all documents
            warning_msg = (
                f"DELETING ALL DOCUMENTS from collection '{self.collection_name}' in database '{self.db_name}'"
            )
            logger.warning(warning_msg)
            self.log(warning_msg)

            # Perform deletion
            deleted_count = collection.delete_many({}).deleted_count
            info_msg = f"Deleted {deleted_count} existing documents (overwrite mode)"
            logger.info(info_msg)
            self.log(info_msg)

        # Insert documents
        if len(documents) == 1:
            result = collection.insert_one(documents[0])
            self.log(f"Inserted 1 document with _id: {result.inserted_id}")
            inserted_ids = [str(result.inserted_id)]
        else:
            result = collection.insert_many(documents)
            self.log(f"Inserted {len(result.inserted_ids)} documents")
            inserted_ids = [str(obj_id) for obj_id in result.inserted_ids]

        return [
            Data(
                data={
                    "operation": "insert",
                    "inserted_ids": inserted_ids,
                    "count": len(inserted_ids),
                }
            )
        ]

    def update_operation(self, collection: Collection) -> list[Data]:
        """Execute update operation."""
        query_filter = self.parse_json(self.search_query)
        update_data = self.parse_json(self.document_data)

        if not update_data:
            msg = "No update data provided. Use 'Document Data' field"
            raise ValueError(msg)

        # Wrap in $set if not already using update operators
        if not any(key.startswith("$") for key in update_data):
            update_data = {"$set": update_data}

        self.log(f"Updating documents with filter: {self._redact_sensitive(query_filter)}")
        self.log(f"Update operation with fields: {self._redact_sensitive(update_data)}")

        if self.update_many:
            result = collection.update_many(query_filter, update_data, upsert=self.upsert)
            self.log(
                f"Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}"
            )
        else:
            result = collection.update_one(query_filter, update_data, upsert=self.upsert)
            self.log(
                f"Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}"
            )

        return [
            Data(
                data={
                    "operation": "update",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count,
                    "upserted_id": (str(result.upserted_id) if result.upserted_id else None),
                }
            )
        ]

    def replace_operation(self, collection: Collection) -> list[Data]:
        """Execute replace operation (replaces entire document)."""
        query_filter = self.parse_json(self.search_query)
        replacement_doc = self.parse_json(self.document_data)

        if not replacement_doc:
            msg = "No replacement document provided. Use 'Document Data' field"
            raise ValueError(msg)

        self.log(f"Replacing document with filter: {self._redact_sensitive(query_filter)}")

        result = collection.replace_one(query_filter, replacement_doc, upsert=self.upsert)
        self.log(f"Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}")

        return [
            Data(
                data={
                    "operation": "replace",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count,
                    "upserted_id": (str(result.upserted_id) if result.upserted_id else None),
                }
            )
        ]

    def delete_operation(self, collection: Collection) -> list[Data]:
        """Execute delete operation."""
        query_filter = self.parse_json(self.search_query)

        if not query_filter:
            msg = "Delete operation requires a filter. Use 'Filter/Query' field"
            raise ValueError(msg)

        self.log(f"Deleting documents with filter: {self._redact_sensitive(query_filter)}")

        if self.update_many:
            result = collection.delete_many(query_filter)
            self.log(f"Deleted {result.deleted_count} documents")
        else:
            result = collection.delete_one(query_filter)
            self.log(f"Deleted {result.deleted_count} document")

        return [Data(data={"operation": "delete", "deleted_count": result.deleted_count})]

    def query_mongodb(self) -> list[Data]:
        """Execute the selected MongoDB operation."""
        collection = self.get_collection()

        operations = {
            "query": self.query_operation,
            "insert": self.insert_operation,
            "update": self.update_operation,
            "replace": self.replace_operation,
            "delete": self.delete_operation,
        }

        operation_func = operations.get(self.operation)
        if not operation_func:
            msg = f"Unknown operation: {self.operation}"
            raise ValueError(msg)

        results = operation_func(collection)
        self.status = results

        return results

    def _query_with_filter(self, query_filter: str | dict) -> list[dict]:
        """Execute query operation with filter for tool mode.

        Args:
            query_filter: MongoDB filter query as JSON string or dict

        Returns:
            List of documents matching the query
        """
        # Handle both string and dict inputs
        if isinstance(query_filter, dict):
            filter_dict = query_filter
        else:
            filter_dict = self.parse_json(query_filter)

        self.log(f"Tool Mode - Executing query with filter: {self._redact_sensitive(filter_dict)}")

        collection = self.get_collection()
        cursor = collection.find(filter_dict).limit(self.limit)

        results = []
        for raw_doc in cursor:
            converted_doc = self.convert_objectid_to_str(raw_doc)
            results.append(converted_doc)

        self.log(f"Tool Mode - Found {len(results)} documents")
        return results

    def _insert_with_data(self, document: str | dict) -> dict:
        """Execute insert operation for tool mode.

        Args:
            document: Document to insert as JSON string or dict

        Returns:
            Result info with inserted IDs
        """
        if isinstance(document, dict):
            doc = document
        else:
            doc = self.parse_json(document)

        self.log(f"Tool Mode - Inserting document with fields: {self._redact_sensitive(doc)}")

        collection = self.get_collection()
        result = collection.insert_one(doc)

        self.log(f"Tool Mode - Inserted document with _id: {result.inserted_id}")
        return {"operation": "insert", "inserted_id": str(result.inserted_id)}

    def _update_with_filter(self, query_filter: str | dict, update: str | dict) -> dict:
        """Execute update operation for tool mode.

        Args:
            query_filter: MongoDB filter query as JSON string or dict
            update: Data to update as JSON string or dict

        Returns:
            Result info with update counts
        """
        if isinstance(query_filter, dict):
            filter_dict = query_filter
        else:
            filter_dict = self.parse_json(query_filter)

        if isinstance(update, dict):
            upd_data = update
        else:
            upd_data = self.parse_json(update)

        # Wrap in $set if not already using update operators
        if not any(key.startswith("$") for key in upd_data):
            upd_data = {"$set": upd_data}

        self.log(f"Tool Mode - Updating documents with filter: {self._redact_sensitive(filter_dict)}")
        self.log(f"Tool Mode - Update operation with fields: {self._redact_sensitive(upd_data)}")

        collection = self.get_collection()

        if self.update_many:
            result = collection.update_many(filter_dict, upd_data, upsert=self.upsert)
            operation = "update_many"
        else:
            result = collection.update_one(filter_dict, upd_data, upsert=self.upsert)
            operation = "update_one"

        self.log(
            f"Tool Mode - Matched: {result.matched_count}, "
            f"Modified: {result.modified_count}, "
            f"Upserted: {result.upserted_id}"
        )
        return {
            "operation": operation,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    def _replace_with_filter(self, query_filter: str | dict, replacement: str | dict) -> dict:
        """Execute replace operation for tool mode.

        Args:
            query_filter: MongoDB filter query as JSON string or dict
            replacement: Document to replace with as JSON string or dict

        Returns:
            Result info with replace counts
        """
        if isinstance(query_filter, dict):
            filter_dict = query_filter
        else:
            filter_dict = self.parse_json(query_filter)

        if isinstance(replacement, dict):
            repl_doc = replacement
        else:
            repl_doc = self.parse_json(replacement)

        self.log(f"Tool Mode - Replacing document with filter: {self._redact_sensitive(filter_dict)}")

        collection = self.get_collection()
        result = collection.replace_one(filter_dict, repl_doc, upsert=self.upsert)

        self.log(
            f"Tool Mode - Matched: {result.matched_count}, "
            f"Modified: {result.modified_count}, "
            f"Upserted: {result.upserted_id}"
        )
        return {
            "operation": "replace",
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    def _delete_with_filter(self, query_filter: str | dict) -> dict:
        """Execute delete operation for tool mode.

        Args:
            query_filter: MongoDB filter query as JSON string or dict

        Returns:
            Result info with deleted count
        """
        if isinstance(query_filter, dict):
            filter_dict = query_filter
        else:
            filter_dict = self.parse_json(query_filter)

        if not filter_dict:
            msg = "Delete operation requires a filter"
            raise ValueError(msg)

        self.log(f"Tool Mode - Deleting documents with filter: {self._redact_sensitive(filter_dict)}")

        collection = self.get_collection()

        if self.update_many:
            result = collection.delete_many(filter_dict)
            operation = "delete_many"
            self.log(f"Tool Mode - Deleted {result.deleted_count} documents")
        else:
            result = collection.delete_one(filter_dict)
            operation = "delete_one"
            self.log(f"Tool Mode - Deleted {result.deleted_count} document")

        return {"operation": operation, "deleted_count": result.deleted_count}

    async def to_toolkit(self) -> list[Tool]:
        """Convert MongoDB component to tools for agent use.

        Only exposes tools for the selected operation to prevent unauthorized writes.

        Returns:
            List containing the MongoDB tool(s) for the selected operation
        """
        tools = []

        if self.operation == "query":
            tool = StructuredTool.from_function(
                name="mongodb_query",
                description=(
                    f"Query documents from MongoDB collection '{self.collection_name}' "
                    f"in database '{self.db_name}'. "
                    "Use this tool to search and retrieve documents using MongoDB query filters. "
                    "Supports standard MongoDB query operators like $gt, $lt, $in, $regex, etc."
                ),
                func=self._query_with_filter,
                args_schema=self.MongoDBQuerySchema,
            )
            tools.append(tool)

        elif self.operation == "insert":
            tool = StructuredTool.from_function(
                name="mongodb_insert",
                description=(
                    f"Insert document(s) into MongoDB collection '{self.collection_name}' in database '{self.db_name}'."
                ),
                func=self._insert_with_data,
                args_schema=self.MongoDBInsertSchema,
            )
            tools.append(tool)

        elif self.operation == "update":
            tool = StructuredTool.from_function(
                name="mongodb_update",
                description=(
                    f"Update document(s) in MongoDB collection '{self.collection_name}' "
                    f"in database '{self.db_name}'. "
                    f"Update mode: {'many' if self.update_many else 'single'}, "
                    f"Upsert: {self.upsert}"
                ),
                func=self._update_with_filter,
                args_schema=self.MongoDBUpdateSchema,
            )
            tools.append(tool)

        elif self.operation == "replace":
            tool = StructuredTool.from_function(
                name="mongodb_replace",
                description=(
                    f"Replace document in MongoDB collection '{self.collection_name}' "
                    f"in database '{self.db_name}'. "
                    f"Upsert: {self.upsert}"
                ),
                func=self._replace_with_filter,
                args_schema=self.MongoDBReplaceSchema,
            )
            tools.append(tool)

        elif self.operation == "delete":
            tool = StructuredTool.from_function(
                name="mongodb_delete",
                description=(
                    f"Delete document(s) from MongoDB collection '{self.collection_name}' "
                    f"in database '{self.db_name}'. "
                    f"Delete mode: {'many' if self.update_many else 'single'}"
                ),
                func=self._delete_with_filter,
                args_schema=self.MongoDBDeleteSchema,
            )
            tools.append(tool)

        return tools
