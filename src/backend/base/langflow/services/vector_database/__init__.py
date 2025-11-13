"""Vector Database Service - Simple and easy to use!

Just import and use:
    from langflow.services.vector_database import VectorDatabaseService

    service = VectorDatabaseService()
    service.store_flow(...)
    results = service.search_flows(...)
"""

from langflow.services.vector_database.service import VectorDatabaseService

__all__ = ["VectorDatabaseService"]
