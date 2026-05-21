"""Read-mostly HTTP surface for the in-flow trigger feature.

Filled in a later commit. For now this is just the router shell so
the API package keeps importing cleanly while the schema refactor
takes effect — the trigger configuration moved into ``flow.data`` and
the old CRUD endpoints no longer apply.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/triggers", tags=["Triggers"])
