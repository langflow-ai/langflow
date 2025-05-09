from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from pymongo import MongoClient
from datetime import datetime

class MongoDBTaskParserSaver(Component):
    display_name = "MongoDB Task Parser & Saver"
    description = "Parse and save tasks from context to MongoDB"
    icon = "🗄️"
    name = "MongoDBTaskParserSaver"

    inputs = [
        MessageTextInput(name="mongo_url", display_name="MongoDB URL", required=True),
        MessageTextInput(name="db_name", display_name="Database Name", required=True),
        MessageTextInput(name="collection_name", display_name="Collection Name", required=True),
        MessageTextInput(name="object_name", display_name="Context Object Name", required=True, info="Key in context, e.g., 'tasks'"),
        MessageTextInput(name="user_id", display_name="User ID", required=True),
    ]
    outputs = [
        Output(display_name="Result", name="result", method="parse_and_save_tasks"),
    ]

    def parse_and_save_tasks(self) -> str:
        mongo_url = self.mongo_url
        db_name = self.db_name
        collection_name = self.collection_name
        object_name = self.object_name
        user_id = self.user_id

        tasks = self.ctx.get(object_name, [])
        if not isinstance(tasks, list):
            return f"Context key '{object_name}' does not contain a list of tasks."

        tasks_to_store = []
        now = datetime.utcnow()
        for t in tasks:
            intent = t.get("intent")
            is_reminder = intent == "REMINDER"
            date = t.get("date")
            time_ = t.get("time")
            # Instead of parsing, just combine as string or leave None
            datetime_str = f"{date} {time_}".strip() if (is_reminder and (date or time_)) else None

            task_doc = {
                "user_id": user_id,
                "intent": intent,
                "content": t.get("content"),
                "date": date,
                "time": time_,
                "datetime": datetime_str,
                "frequency": t.get("frequency", "once"),
                "people": t.get("people", []),
                "tags": t.get("tags", []),
                "status": "active" if is_reminder else "archived",
                "source": "langflow",
                "created_at": now,
                "updated_at": now,
            }
            tasks_to_store.append(task_doc)

        try:
            client = MongoClient(mongo_url)
            db = client[db_name]
            collection = db[collection_name]
            if tasks_to_store:
                result = collection.insert_many(tasks_to_store)
                return f"Inserted {len(result.inserted_ids)} tasks."
            else:
                return "No tasks to insert."
        except Exception as e:
            self.log(f"Error saving tasks to MongoDB: {e}")
            return f"Error: {e}" 