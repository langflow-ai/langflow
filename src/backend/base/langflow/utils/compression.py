import gzip
import json
from typing import Any

from fastapi import Response
from fastapi.encoders import jsonable_encoder


def compress_response(data: Any) -> Response:
    """Compress data and return it as a FastAPI Response with appropriate headers."""
    json_data = json.dumps(jsonable_encoder(data)).encode("utf-8")

    compressed_data = gzip.compress(json_data, compresslevel=6)

    return Response(
        content=compressed_data,
        media_type="application/json",
        headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding", "Content-Length": str(len(compressed_data))},
    )
