from sqlalchemy import select

from langflow.services.database.models.folder.model import Folder


async def generate_unique_folder_name(folder_name, user_id, session):
    original_name = folder_name
    n = 1
    while True:
        # Check if a project with the given name exists
        existing_folder = (
            await session.exec(
                select(Folder).where(
                    Folder.name == folder_name,
                    Folder.user_id == user_id,
                )
            )
        ).first()

        # If no project with the given name exists, return the name
        if not existing_folder:
            return folder_name

        # If a project with the name already exists, append (n) to the name and increment n
        folder_name = f"{original_name} ({n})"
        n += 1
