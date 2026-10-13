"""Run the real container reader and strict app importer on synthetic stores.

uv run --no-sync python tools/chroma_migration_helper/qualify.py --image <built-image>
The image tag argument is allowed only in this test harness. The production
launcher always requires its signed release digest.
"""

# This standalone qualification process serially drives its own synthetic test
# containers. It is not an application event loop or an untrusted command API.
# Private helpers are deliberately exercised as production qualification targets.
# ruff: noqa: ASYNC221, S603, SLF001

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from langflow.services.knowledge_base_storage import helper
from langflow.services.knowledge_base_storage.helper import isolated_command
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
from lfx.base.knowledge_bases.migration.importer import import_qualified_export
from lfx.base.knowledge_bases.migration.protocol import qualify_export


async def qualify(image: str, *, signed: bool = False) -> dict:
    """Exercise the isolated reader against the supported legacy-store qualification cases."""
    docker = shutil.which("docker")
    if not docker:
        msg = "Docker is required for actual helper containment qualification"
        raise RuntimeError(msg)
    source_image = image
    if signed:
        if os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_IMAGE") != image:
            msg = "Signed qualification requires the exact configured release image"
            raise ValueError(msg)
        cosign = shutil.which("cosign")
        if not cosign or not os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_BUNDLE"):
            msg = "Signed qualification requires offline production verification material"
            raise ValueError(msg)
        # The fixture generator also selects only the verified immutable content.
        source_image = await helper._stage_verified_helper(docker, cosign, image)
    scratch_parent = os.environ.get("LANGFLOW_HELPER_TEST_TMPDIR")
    with tempfile.TemporaryDirectory(prefix="langflow-helper-qualification-", dir=scratch_parent) as scratch:
        root = Path(scratch).resolve()
        uid = os.getuid() if hasattr(os, "getuid") else 10001
        if uid == 0:
            root.chmod(0o777)
        fixture = Path(__file__).with_name("create_fixture.py").read_bytes()
        subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--pull=never",
                "--network=none",
                "--user",
                str(uid or 10001),
                "--mount",
                f"type=bind,source={root},target=/fixture",
                "--entrypoint",
                "python",
                "--interactive",
                source_image,
                "-",
            ],
            input=fixture,
            check=True,
            timeout=120,
        )
        expected = json.loads((root / "expected.json").read_text())
        persisted = list((root / "source").glob("*/index_metadata.pickle"))
        if not persisted:
            msg = "Fixture failed to produce a persisted HNSW index"
            raise AssertionError(msg)
        containment = """
import os, socket
assert "LANGFLOW_HELPER_TEST_SECRET" not in os.environ
assert os.getuid() != 0
try:
    open("/source/forbidden-write", "w").close()
except OSError:
    pass
else:
    raise AssertionError("Snapshot mount is writable")
try:
    socket.create_connection(("1.1.1.1", 443), timeout=1).close()
except OSError:
    pass
else:
    raise AssertionError("Helper has external network access")
"""
        isolated = isolated_command(docker, source_image, root / "source", f"lf-helper-boundary-{uuid4().hex}")
        subprocess.run(
            [*isolated[:-1], "--entrypoint", "python", source_image, "-c", containment],
            check=True,
            timeout=30,
            capture_output=True,
            env={
                **os.environ,
                "LANGFLOW_HELPER_TEST_SECRET": "synthetic",  # pragma: allowlist secret
            },
        )
        total = 0
        for metric in ("l2", "cosine", "ip", "empty"):
            request = {
                "collection_name": f"fixture-{metric}",
                "source_id": str(uuid4()),
                "source_fingerprint": hashlib.sha256(f"fixture-{metric}".encode()).hexdigest(),
                "model_fingerprint": None,
            }
            output = root / f"{metric}.jsonl"
            # Qualify the exact production create/start/stream/cleanup path.
            # Signing is a separate release gate. Only artifact staging is
            # replaced here, since this synthetic image has not been published.
            if signed:
                header = await helper.export_snapshot(root / "source", output, **request)
            else:
                which = shutil.which
                with (
                    patch.dict(
                        os.environ,
                        {
                            "LANGFLOW_KB_MIGRATION_HELPER_IMAGE": (
                                "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
                            )
                        },
                    ),
                    patch.object(helper, "_stage_verified_helper", AsyncMock(return_value=image)),
                    patch.object(
                        helper.shutil,
                        "which",
                        side_effect=lambda tool, resolve=which: docker if tool == "cosign" else resolve(tool),
                    ),
                ):
                    header = await helper.export_snapshot(root / "source", output, **request)
            backend = SQLiteBackend(
                kb_name=f"fixture-{metric}",
                backend_config={"metric": header.metric},
                storage_context=SQLiteStorageContext(root=root / "destination", owner_id=uuid4(), kb_id=uuid4()),
                create=True,
            )
            await backend.ensure_ready()
            with output.open("rb") as stream, qualify_export(stream, expected_header=header) as source:
                await import_qualified_export(source, backend, migration_id=uuid4())
            records = {}
            async for batch in backend.iter_documents(include_embeddings=True):
                for record in batch:
                    records[record.id] = {
                        "content": record.content,
                        "metadata": record.metadata,
                        "embedding": record.embedding,
                    }
            if records != expected.get(metric, {}):
                msg = "Destination differs from trusted source fixture"
                raise AssertionError(msg)
            if header.dimensions != len([1.0, 2.0, 3.0, 4.0]):
                msg = "Known dimension, including empty-store dimension, was lost"
                raise AssertionError(msg)
            total += len(records)
        # Inject invalid native index metadata on a disposable copy. The native
        # reader must fail without emitting a successful terminal manifest.
        corrupted = root / "corrupted"
        shutil.copytree(root / "source", corrupted)
        for path in corrupted.glob("*/index_metadata.pickle"):
            path.write_bytes(b"not a pickle or a supported native index")
        failed = subprocess.run(
            isolated_command(docker, source_image, corrupted, f"lf-helper-corrupt-{uuid4().hex}"),
            input=json.dumps({**request, "collection_name": "fixture-l2"}).encode(),
            capture_output=True,
            timeout=120,
            check=False,
        )
        if failed.returncode == 0 or b'"type":"complete"' in failed.stdout:
            msg = "Malformed native input was accepted"
            raise AssertionError(msg)
        print(  # noqa: T201 -- standalone qualification evidence for CI
            f"Qualified {total} records across L2/cosine/inner-product and a known-dimension empty store. "
            f"Persisted indexes: {len(persisted)}. Production reader creation, streaming and cleanup passed. "
            "Stored trust_remote_code embedding configuration remained inert. "
            "Network, source-write and credential isolation passed; malformed native input rejected."
        )
        return {"records": total, "persisted_indexes": len(persisted), "hostile_embedding_configuration": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--signed", action="store_true", help="Use the unmodified offline production verification path")
    args = parser.parse_args()
    asyncio.run(qualify(args.image, signed=args.signed))
