"""Run YouTube Extended Search through a Langflow JSON-to-Message flow.

Run with: lfx run youtube_search_extended.py
Set FLASHDATA_API_KEY in the process environment. Execution uses FlashData
Credits for query examples; the download example only reads an existing job.
No language model is called. This is a source example, not a Gallery template.
"""

import os

from lfx.components.processing.parser import ParserComponent
from lfx.graph import Graph
from lfx_flashdata import FlashDataYouTubeSearchExtendedComponent
from pydantic import SecretStr


def get_graph() -> Graph:
    source = FlashDataYouTubeSearchExtendedComponent(
        api_key="FLASHDATA_API_KEY", query="retrieval evaluation tutorials", parameters='{"max_results": 50}'
    )
    parser = ParserComponent(mode="Parser", pattern="{text}")
    parser.set(input_data=source.flashdata_youtube_search_extended)
    graph = Graph(source, parser)
    graph.context.update(
        {
            "request_variables": {"FLASHDATA_API_KEY": SecretStr(os.environ["FLASHDATA_API_KEY"])},
            "no_env_fallback": True,
        }
    )
    return graph
