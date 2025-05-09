from pydantic import BaseModel, Field
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import MessageTextInput, SecretStrInput, HandleInput
from langflow.schema import Data
from langflow.schema.message import Message
from datetime import datetime
from typing import Optional, List
from langflow.logging import logger
import asyncio
import threading

# Optional: Twilio for SMS
try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioClient = None

from pymongo import MongoClient

class ReminderToolComponent(LCToolComponent):
    display_name = "Reminder Tool"
    description = "Schedule reminders and send SMS notifications. Integrates with external memory nodes."
    icon = "alarm"
    name = "ReminderTool"
    action_description = "Schedule a reminder for a user, retrieve reminders, and send SMS notifications."

    inputs = [
        MessageTextInput(name="reminder_text", display_name="Reminder Text", required=False, info="The reminder message. Leave blank to retrieve reminders.", tool_mode=True),
        MessageTextInput(name="reminder_time", display_name="Reminder Time (ISO)", required=False, info="When to send the reminder (ISO format, e.g., 2024-06-10T15:30:00). Leave blank to retrieve reminders.", tool_mode=True),
        MessageTextInput(name="user_id", display_name="User ID", required=False, info="User identifier for the reminder.", tool_mode=True),
        MessageTextInput(name="phone_number", display_name="Phone Number", required=False, info="Phone number to send the SMS reminder to.", tool_mode=True),
        HandleInput(name="memory", display_name="External Memory", input_types=["Memory"], required=False, info="External memory node to store reminders. If empty, will use MongoDB."),
        SecretStrInput(name="mongo_url", display_name="MongoDB URL", required=False, info="MongoDB connection string (e.g., mongodb+srv://user:pass@host/db)"),
        MessageTextInput(name="db_name", display_name="Database Name", required=False, info="Name of the MongoDB database."),
        MessageTextInput(name="collection_name", display_name="Collection Name", required=False, info="Name of the collection to store reminders."),
        SecretStrInput(name="twilio_sid", display_name="Twilio Account SID", required=False, info="Twilio Account SID for SMS sending."),
        SecretStrInput(name="twilio_token", display_name="Twilio Auth Token", required=False, info="Twilio Auth Token for SMS sending."),
        MessageTextInput(name="twilio_from", display_name="Twilio From Number", required=False, info="Twilio phone number to send SMS from."),
    ]

    class ReminderToolSchema(BaseModel):
        reminder_text: Optional[str] = Field(None, description="Reminder message. If blank, retrieves reminders.")
        reminder_time: Optional[str] = Field(None, description="When to send the reminder (ISO format). If blank, retrieves reminders.")
        user_id: Optional[str] = Field(None, description="User identifier. If blank, will be taken from session/context.")
        phone_number: Optional[str] = Field(None, description="Phone number for SMS.")

    def run_model(self) -> List[Data]:
        # If reminder_text is blank, retrieve reminders
        if not self.reminder_text:
            return self._retrieve_reminders(self.user_id)
        # Otherwise, schedule reminder
        return self._schedule_reminder(
            self.user_id,
            self.reminder_text,
            self.reminder_time,
            self.phone_number
        )

    def build_tool(self) -> Tool:
        return Tool.from_function(
            name="reminder_tool",
            description="Schedule a reminder or retrieve all reminders for a user. If reminder_text is blank, retrieves reminders.",
            func=self._tool_func,
            args_schema=self.ReminderToolSchema,
        )

    def _get_collection(self):
        logger.info(f"Connecting to MongoDB: {self.mongo_url}, DB: {self.db_name}, Collection: {self.collection_name}")
        client = MongoClient(self.mongo_url)
        db = client[self.db_name]
        collection = db[self.collection_name]
        return client, collection

    def _store_reminder_mongo(self, user_id: str, reminder_text: str, reminder_time: datetime, phone_number: str) -> List[Data]:
        client, collection = self._get_collection()
        try:
            reminder_doc = {
                "user_id": user_id,
                "reminder_text": reminder_text,
                "reminder_time": reminder_time,
                "phone_number": phone_number,
                "created_at": datetime.utcnow(),
                "sent": False,
            }
            logger.info(f"Inserting reminder: {reminder_doc}")
            collection.insert_one(reminder_doc)
            return [Data(data={"result": f"Reminder scheduled for user {user_id}", "reminder": reminder_text, "reminder_time": str(reminder_time)})]
        except Exception as e:
            logger.error(f"Error inserting reminder: {e}")
            return [Data(data={"error": str(e)})]
        finally:
            client.close()

    def _retrieve_reminders_mongo(self, user_id: str) -> List[Data]:
        client, collection = self._get_collection()
        try:
            reminders = list(collection.find({"user_id": user_id}))
            reminders_data = [
                {
                    "reminder_text": r.get("reminder_text", ""),
                    "reminder_time": str(r.get("reminder_time", "")),
                    "sent": r.get("sent", False),
                }
                for r in reminders
            ]
            return [Data(data={"result": f"Retrieved {len(reminders_data)} reminders for user {user_id}", "reminders": reminders_data})]
        finally:
            client.close()

    def _store_reminder_memory(self, memory, user_id: str, reminder_text: str, reminder_time: datetime, phone_number: str) -> List[Data]:
        # Store as a Message with properties
        msg = Message(
            text=reminder_text,
            sender="system",
            sender_name="ReminderTool",
            session_id=user_id,
            properties={
                "reminder_time": str(reminder_time),
                "phone_number": phone_number,
                "sent": False,
            },
        )
        # Use async add (run in thread for sync context)
        loop = asyncio.get_event_loop()
        coro = memory.aadd_messages([msg.to_lc_message()])
        loop.run_until_complete(coro)
        return [Data(data={"result": f"Reminder scheduled for user {user_id}", "reminder": reminder_text, "reminder_time": str(reminder_time)})]

    def _retrieve_reminders_memory(self, memory, user_id: str) -> List[Data]:
        loop = asyncio.get_event_loop()
        coro = memory.aget_messages()
        messages = loop.run_until_complete(coro)
        reminders = [Message.from_lc_message(m) for m in messages if getattr(m, "session_id", None) == user_id]
        reminders_data = [
            {
                "reminder_text": r.text,
                "reminder_time": r.properties.get("reminder_time", ""),
                "sent": r.properties.get("sent", False),
            }
            for r in reminders
        ]
        return [Data(data={"result": f"Retrieved {len(reminders_data)} reminders for user {user_id}", "reminders": reminders_data})]

    def _schedule_reminder(self, user_id: str, reminder_text: str, reminder_time: datetime, phone_number: str) -> List[Data]:
        # Use memory node if provided
        if self.memory:
            result = self._store_reminder_memory(self.memory, user_id, reminder_text, reminder_time, phone_number)
        else:
            result = self._store_reminder_mongo(user_id, reminder_text, reminder_time, phone_number)
        # Schedule SMS sending in background
        if reminder_time and phone_number:
            threading.Thread(target=self._schedule_sms, args=(user_id, reminder_text, reminder_time, phone_number)).start()
        return result

    def _retrieve_reminders(self, user_id: str) -> List[Data]:
        if self.memory:
            return self._retrieve_reminders_memory(self.memory, user_id)
        else:
            return self._retrieve_reminders_mongo(user_id)

    def _schedule_sms(self, user_id: str, reminder_text: str, reminder_time: datetime, phone_number: str):
        # Wait until the scheduled time
        now = datetime.utcnow()
        delay = (reminder_time - now).total_seconds()
        if delay > 0:
            threading.Event().wait(delay)
        # Send SMS
        self._send_sms(phone_number, reminder_text)
        # Mark as sent in storage (optional, not implemented for all backends)

    def _send_sms(self, phone_number: str, reminder_text: str):
        if TwilioClient and self.twilio_sid and self.twilio_token and self.twilio_from:
            client = TwilioClient(self.twilio_sid, self.twilio_token)
            try:
                client.messages.create(
                    body=reminder_text,
                    from_=self.twilio_from,
                    to=phone_number,
                )
            except Exception as e:
                print(f"Failed to send SMS: {e}")
        else:
            print(f"SMS to {phone_number}: {reminder_text} (Twilio not configured)")

    def _tool_func(self, reminder_text=None, reminder_time=None, user_id=None, phone_number=None):
        # Prefer explicit input, fallback to self.user_id (from context/graph)
        user_id = user_id or self.user_id
        if not user_id:
            return [Data(data={"error": "user_id must be provided as input or in context/session."})]
        if not reminder_text:
            return self._retrieve_reminders(user_id)
        if self.reminder_time:
            reminder_time = datetime.fromisoformat(self.reminder_time)
        else:
            reminder_time = None
        return self._schedule_reminder(user_id, reminder_text, reminder_time, phone_number) 