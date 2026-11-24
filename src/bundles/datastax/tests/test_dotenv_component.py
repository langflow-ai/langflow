import os

import pytest
from lfx_datastax.components.datastax.dotenv import Dotenv


def test_dotenv_is_retired_without_changing_process_configuration(monkeypatch):
    monkeypatch.setenv("LANGFLOW_DOTENV_TEST_LABEL", "server")
    component = Dotenv(dotenv_file_content="LANGFLOW_DOTENV_TEST_LABEL=flow")

    with pytest.raises(ValueError, match="Replace it with Langflow global variables"):
        component.process_inputs()

    assert os.environ["LANGFLOW_DOTENV_TEST_LABEL"] == "server"
