import json
import re
from typing import Union

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


class MongoDBQueryComponent(Component):
    display_name = "MongoDB NoSQL"
    description = "MongoDB NoSQL Component with CRUD operations"
    name = "MongoDBNoSQL"
    icon = "MongoDB"
    OPERATIONS = ["query", "insert", "update", "delete", "replace"]
    INSERT_MODES = ["append", "overwrite"]

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
    ]

    outputs = [
        Output(display_name="Results", name="results", method="query_mongodb"),
    ]

    class MongoDBQuerySchema(BaseModel):
        """Schema for MongoDB query tool."""

        filter: Union[str, dict] = Field(
            ...,
            description="MongoDB filter query as JSON string or dict. Examples: "
            '{"title": "Movie Name"} or {"year": {"$gt": 2020}} or {} for all documents.',
        )

    class MongoDBInsertSchema(BaseModel):
        """Schema for MongoDB insert tool."""

        document: Union[str, dict] = Field(
            ...,
            description="Document(s) to insert as JSON. Examples: "
            '{"title": "New Movie", "runtime": 120}',
        )

    class MongoDBUpdateSchema(BaseModel):
        """Schema for MongoDB update tool."""

        filter: Union[str, dict] = Field(
            ...,
            description="MongoDB filter to find documents to update. Examples: "
            '{"title": "Movie Name"} or {"session_id": "uuid-123456789"}',
        )
        update: Union[str, dict] = Field(
            ...,
            description='Data to update as JSON. Examples: {"runtime": 120} or {"$set": {"sinais_vitais.temperatura": 40}}',
        )

    class MongoDBReplaceSchema(BaseModel):
        """Schema for MongoDB replace tool."""

        filter: Union[str, dict] = Field(
            ...,
            description="MongoDB filter to find document to replace. Examples: "
            '{"title": "Movie Name"} or {"session_id": "uuid-123456789"}',
        )
        replacement: Union[str, dict] = Field(
            ...,
            description="New document to replace with as JSON. Examples: "
            '{"title": "Updated Movie", "runtime": 150}',
        )

    class MongoDBDeleteSchema(BaseModel):
        """Schema for MongoDB delete tool."""

        filter: Union[str, dict] = Field(
            ...,
            description="MongoDB filter to find documents to delete. Examples: "
            '{"title": "Movie Name"} or {"session_id": "uuid-123456789"}',
        )

    def parse_json(self, json_string: str) -> dict:
        """Parse JSON string to dict.

        Accepts both formats:
        - {"title": "value", "runtime": 11}  (standard JSON)
        - {title:'value',runtime:11}  (JavaScript-like)
        """
        if not json_string or json_string.strip() in ["{}", ""]:
            return {}

        try:
            # Try parsing as standard JSON first
            return json.loads(json_string)
        except json.JSONDecodeError:
            # Try to fix JavaScript-like format
            try:
                # Replace single quotes with double quotes
                fixed_json = json_string.replace("'", '"')

                # Add quotes around unquoted keys
                fixed_json = re.sub(
                    r"(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', fixed_json
                )

                return json.loads(fixed_json)
            except json.JSONDecodeError as e:
                msg = f"Invalid JSON format: {e}\n\nExpected format:\n{{'key':'value'}}\nor\n{{\"key\":\"value\"}}"
                raise ValueError(msg) from e

    def get_collection(self) -> Collection:
        """Build MongoDB connection and return collection."""
        try:
            from pymongo import MongoClient
        except ImportError as e:
            msg = "Please install pymongo to use MongoDB NoSQL"
            raise ImportError(msg) from e

        try:
            mongo_client: MongoClient = MongoClient(self.mongodb_nosql_uri)
            collection = mongo_client[self.db_name][self.collection_name]
            return collection

        except Exception as e:
            msg = f"Failed to connect to MongoDB NoSQL: {e}"
            raise ValueError(msg) from e

    def convert_objectid_to_str(self, doc: dict) -> dict:
        """Convert ObjectId fields to strings for serialization."""
        from bson.objectid import ObjectId

        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
        return doc

    def query_operation(self, collection: Collection) -> list[Data]:
        """Execute query operation."""
        query_filter = self.parse_json(self.search_query)
        self.log(f"Executing query: {query_filter}")

        cursor = collection.find(query_filter).limit(self.limit)

        results = []
        for doc in cursor:
            doc = self.convert_objectid_to_str(doc)
            results.append(Data(data=doc))

        self.log(f"Found {len(results)} documents")
        return results

    def insert_operation(self, collection: Collection) -> list[Data]:
        """Execute insert operation."""
        documents = []

        # Check for bulk insert data
        if self.ingest_data:
            for _input in self.ingest_data:
                if isinstance(_input, Data):
                    doc_dict = (
                        _input.data if hasattr(_input, "data") else _input.__dict__
                    )
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
            deleted_count = collection.delete_many({}).deleted_count
            self.log(f"Deleted {deleted_count} existing documents (overwrite mode)")

        # Insert documents
        if len(documents) == 1:
            result = collection.insert_one(documents[0])
            self.log(f"Inserted 1 document with _id: {result.inserted_id}")
            inserted_ids = [str(result.inserted_id)]
        else:
            result = collection.insert_many(documents)
            self.log(f"Inserted {len(result.inserted_ids)} documents")
            inserted_ids = [str(id) for id in result.inserted_ids]

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
        if not any(key.startswith("$") for key in update_data.keys()):
            update_data = {"$set": update_data}

        self.log(f"Updating documents matching: {query_filter}")
        self.log(f"Update operation: {update_data}")

        if self.update_many:
            result = collection.update_many(
                query_filter, update_data, upsert=self.upsert
            )
            self.log(
                f"Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}"
            )
        else:
            result = collection.update_one(
                query_filter, update_data, upsert=self.upsert
            )
            self.log(
                f"Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}"
            )

        return [
            Data(
                data={
                    "operation": "update",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count,
                    "upserted_id": (
                        str(result.upserted_id) if result.upserted_id else None
                    ),
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

        self.log(f"Replacing document matching: {query_filter}")

        result = collection.replace_one(
            query_filter, replacement_doc, upsert=self.upsert
        )
        self.log(
            f"Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}"
        )

        return [
            Data(
                data={
                    "operation": "replace",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count,
                    "upserted_id": (
                        str(result.upserted_id) if result.upserted_id else None
                    ),
                }
            )
        ]

    def delete_operation(self, collection: Collection) -> list[Data]:
        """Execute delete operation."""
        query_filter = self.parse_json(self.search_query)

        if not query_filter:
            msg = "Delete operation requires a filter. Use 'Filter/Query' field"
            raise ValueError(msg)

        self.log(f"Deleting documents matching: {query_filter}")

        if self.update_many:
            result = collection.delete_many(query_filter)
            self.log(f"Deleted {result.deleted_count} documents")
        else:
            result = collection.delete_one(query_filter)
            self.log(f"Deleted {result.deleted_count} document")

        return [
            Data(data={"operation": "delete", "deleted_count": result.deleted_count})
        ]

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

    def _query_with_filter(self, filter: Union[str, dict]) -> list[dict]:
        """Execute query operation with filter for tool mode.

        Args:
            filter: MongoDB filter query as JSON string or dict

        Returns:
            List of documents matching the query
        """
        # Handle both string and dict inputs
        if isinstance(filter, dict):
            query_filter = filter
        else:
            query_filter = self.parse_json(filter)

        self.log(f"Tool Mode - Executing query: {query_filter}")

        collection = self.get_collection()
        cursor = collection.find(query_filter).limit(self.limit)

        results = []
        for doc in cursor:
            doc = self.convert_objectid_to_str(doc)
            results.append(doc)

        self.log(f"Tool Mode - Found {len(results)} documents")
        return results

    def _insert_with_data(self, document: Union[str, dict]) -> dict:
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

        self.log(f"Tool Mode - Inserting document: {doc}")

        collection = self.get_collection()
        result = collection.insert_one(doc)

        self.log(f"Tool Mode - Inserted document with _id: {result.inserted_id}")
        return {"operation": "insert", "inserted_id": str(result.inserted_id)}

    def _update_with_filter(self, filter: Union[str, dict], update: Union[str, dict]) -> dict:
        """Execute update operation for tool mode.

        Args:
            filter: MongoDB filter query as JSON string or dict
            update: Data to update as JSON string or dict

        Returns:
            Result info with update counts
        """
        if isinstance(filter, dict):
            query_filter = filter
        else:
            query_filter = self.parse_json(filter)

        if isinstance(update, dict):
            upd_data = update
        else:
            upd_data = self.parse_json(update)

        # Wrap in $set if not already using update operators
        if not any(key.startswith("$") for key in upd_data.keys()):
            upd_data = {"$set": upd_data}

        self.log(f"Tool Mode - Updating documents matching: {query_filter}")
        self.log(f"Tool Mode - Update operation: {upd_data}")

        collection = self.get_collection()
        result = collection.update_many(query_filter, upd_data, upsert=self.upsert)

        self.log(
            f"Tool Mode - Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}"
        )
        return {
            "operation": "update",
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    def _replace_with_filter(self, filter: Union[str, dict], replacement: Union[str, dict]) -> dict:
        """Execute replace operation for tool mode.

        Args:
            filter: MongoDB filter query as JSON string or dict
            replacement: Document to replace with as JSON string or dict

        Returns:
            Result info with replace counts
        """
        if isinstance(filter, dict):
            query_filter = filter
        else:
            query_filter = self.parse_json(filter)

        if isinstance(replacement, dict):
            repl_doc = replacement
        else:
            repl_doc = self.parse_json(replacement)

        self.log(f"Tool Mode - Replacing document matching: {query_filter}")

        collection = self.get_collection()
        result = collection.replace_one(query_filter, repl_doc, upsert=self.upsert)

        self.log(
            f"Tool Mode - Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}"
        )
        return {
            "operation": "replace",
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    def _delete_with_filter(self, filter: Union[str, dict]) -> dict:
        """Execute delete operation for tool mode.

        Args:
            filter: MongoDB filter query as JSON string or dict

        Returns:
            Result info with deleted count
        """
        if isinstance(filter, dict):
            query_filter = filter
        else:
            query_filter = self.parse_json(filter)

        if not query_filter:
            msg = "Delete operation requires a filter"
            raise ValueError(msg)

        self.log(f"Tool Mode - Deleting documents matching: {query_filter}")

        collection = self.get_collection()
        result = collection.delete_many(query_filter)

        self.log(f"Tool Mode - Deleted {result.deleted_count} documents")
        return {"operation": "delete", "deleted_count": result.deleted_count}

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
                    f"Insert document(s) into MongoDB collection '{self.collection_name}' "
                    f"in database '{self.db_name}'."
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
