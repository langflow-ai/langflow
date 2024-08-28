import json
import os.path
import shutil

# we need to import tmpdir
import tempfile
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

import orjson
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from typer.testing import CliRunner

from langflow.graph.graph.base import Graph
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User, UserCreate
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service

def get_required_env_var(var: str) -> str:
    """
    Get the value of the specified environment variable.

    Args:
    var (str): The environment variable to get.

    Returns:
    str: The value of the environment variable.

    Raises:
    ValueError: If the environment variable is not set.
    """
    value = os.getenv(var)
    if not value:
        raise ValueError(f"Environment variable {var} is not set")
    return value

def get_openai_api_key() -> str:
    return get_required_env_var("OPENAI_API_KEY")

def get_astradb_application_token() -> str:
    return get_required_env_var("ASTRA_DB_APPLICATION_TOKEN")

def get_astradb_api_endpoint() -> str:
    return get_required_env_var("ASTRA_DB_API_ENDPOINT")
