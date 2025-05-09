from pydantic import BaseModel, Field
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import MessageTextInput, SecretStrInput
from langflow.schema import Data
from pymongo import MongoClient
from datetime import datetime
from langchain_core.tools import StructuredTool

class NoteTakingToolComponent(LCToolComponent):
    display_name = "Note Taking (MongoDB)"
    description = "Store and retrieve notes using MongoDB. Future-proof for reminders and more."
    icon = "edit"
    name = "NoteTakingTool"
    action_description = "Store a note for the user or retrieve all notes. To store, provide a note. To retrieve, leave note blank."

    inputs = [
        SecretStrInput(
            name="mongo_url",
            display_name="MongoDB URL",
            required=True,
            info="MongoDB connection string (e.g., mongodb+srv://user:pass@host/db)"
        ),
        MessageTextInput(
            name="db_name",
            display_name="Database Name",
            required=True,
            info="Name of the MongoDB database."
        ),
        MessageTextInput(
            name="collection_name",
            display_name="Collection Name",
            required=True,
            info="Name of the collection to store notes."
        ),
        MessageTextInput(
            name="user_id",
            display_name="User ID",
            required=False,
            info="User identifier for storing/retrieving notes. If not provided, will be taken from context."
        ),
        MessageTextInput(
            name="note",
            display_name="Note",
            info="The note you want to store. Leave blank to retrieve all notes.",
            required=False,
            tool_mode=True,
        ),
    ]

    class NoteToolSchema(BaseModel):
        user_id: str = Field(None, description="User identifier. If blank, will be taken from context.")
        note: str = Field(None, description="The note to store. If blank, retrieves notes.")

    def run_model(self) -> list[Data]:
        user_id = 'test' #self.user_id
        if not user_id:
            return [Data(data={"error": "user_id must be provided as input or in context."})]
        if self.note:
            return self._store_note(user_id, self.note)
        else:
            return self._retrieve_notes(user_id)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="note_taking",
            description="Store a note or retrieve all notes for a user from MongoDB. user_id can be provided as input or taken from context.",
            func=self._tool_func,
            args_schema=self.NoteToolSchema,
        )

    def _get_collection(self):
        client = MongoClient(self.mongo_url)
        db = client[self.db_name]
        collection = db[self.collection_name]
        return client, collection

    def _store_note(self, user_id: str, note: str) -> list[Data]:
        client, collection = self._get_collection()
        try:
            note_doc = {
                "user_id": user_id,
                "note": note,
                "created_at": datetime.utcnow(),
            }
            collection.insert_one(note_doc)
            return [Data(data={"result": f"Note stored for user {user_id}", "note": note})]
        finally:
            client.close()

    def _retrieve_notes(self, user_id: str) -> list[Data]:
        client, collection = self._get_collection()
        try:
            notes = list(collection.find({"user_id": user_id}))
            notes_text = [n.get("note", "") for n in notes]
            return [Data(data={"result": f"Retrieved {len(notes_text)} notes for user {user_id}", "notes": notes_text})]
        finally:
            client.close()

    def _tool_func(self, note: str = None, user_id: str = None) -> list[Data]:
        user_id = 'test' #user_id
        if not user_id:
            return [Data(data={"error": "user_id must be provided as input or in context."})]
        if note:
            return self._store_note(user_id, note)
        else:
            return self._retrieve_notes(user_id)