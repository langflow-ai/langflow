"""Inventory released component sources before retiring their provider dependencies.

Run with ``uv run python scripts/update_legacy_storage_sources.py`` from a clone
containing the release tags. Tests use the checked-in distinct source fixtures
and do not require Git history or install retired providers.
"""

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

from lfx.custom import validate
from lfx.custom.legacy_storage_compat import source_fingerprint

MAX_LEGACY_MINOR = 12
ROOT = Path(__file__).resolve().parents[1]
LFX = ROOT / "src/lfx"
INVENTORY = LFX / "src/lfx/_assets/legacy_storage_sources.json"
FIXTURES = LFX / "tests/unit/custom/component/historical_storage_source_fixtures.json"
MODULES = {
    "KnowledgeComponent": "lfx.components.files_and_knowledge.knowledge",
    "KnowledgeIngestionComponent": "lfx.components.files_and_knowledge.ingestion",
    "KnowledgeBaseComponent": "lfx.components.files_and_knowledge.retrieval",
    "KnowledgeRetrievalComponent": "lfx.components.files_and_knowledge.retrieval",
    "MemoryRetrievalComponent": "lfx.components.files_and_knowledge.memory_retrieval",
    "MemoryBaseComponent": "lfx.components.files_and_knowledge.memory_retrieval",
    "ChromaVectorStoreComponent": "lfx.components.chroma.chroma",
    "LocalDBComponent": "lfx.components.chroma.local_db",
    "ALTKAgentComponent": "lfx.components.altk.altk_agent",
}
TARGET_CLASSES = {
    "MemoryRetrievalComponent": "MemoryBaseComponent",
    "KnowledgeRetrievalComponent": "KnowledgeBaseComponent",
}


def git(*args: str) -> str:
    """Read committed release source without changing the checkout."""
    return subprocess.check_output([shutil.which("git") or "git", "-C", str(ROOT), *args], text=True)  # noqa: S603 -- fixed read-only Git commands and locally enumerated refs


def main() -> None:
    """Merge all distinct released module and class fingerprints into the inventory."""
    inventory = json.loads(INVENTORY.read_text())
    entries = {entry["sha256"]: entry for entry in inventory["entries"]}
    fixtures = {}
    tags = [
        tag
        for tag in git("tag", "--list").splitlines()
        if (match := re.fullmatch(r"v?1\.(\d+)\.\d+", tag)) and int(match[1]) <= MAX_LEGACY_MINOR
    ]
    for tag in sorted(tags):
        commit = git("rev-parse", f"{tag}^{{commit}}").strip()
        paths = [
            path
            for path in git("ls-tree", "-r", "--name-only", tag).splitlines()
            if "/components/" in path
            and path.endswith(".py")
            and re.search(r"chroma|local_?db|knowledge|memory|retrieval|ingestion|altk", path, re.IGNORECASE)
        ]
        for path in paths:
            source = git("show", f"{tag}:{path}")
            tree = ast.parse(source)
            for node in tree.body:
                if not isinstance(node, ast.ClassDef) or node.name not in MODULES:
                    continue
                module = MODULES[node.name]
                target_class = TARGET_CLASSES.get(node.name, node.name)
                for kind, code in (("module", source), ("class", ast.get_source_segment(source, node))):
                    if kind == "module" and validate.extract_class_name(source) != node.name:
                        continue
                    fingerprint = source_fingerprint(code)
                    entry = entries.setdefault(
                        fingerprint,
                        {"sha256": fingerprint, "module": module, "class_name": target_class, "sources": []},
                    )
                    if (entry["module"], entry["class_name"]) != (module, target_class):
                        msg = f"Ambiguous released component fingerprint: {tag}:{path}:{node.name}"
                        raise ValueError(msg)
                    evidence = {"commit": commit, "path": path, "kind": kind, "tag": tag}
                    if evidence not in entry["sources"]:
                        entry["sources"].append(evidence)
                    fixtures.setdefault(
                        fingerprint, {"tag": tag, "path": path, "class_name": target_class, "source": code}
                    )
    inventory["entries"] = sorted(entries.values(), key=lambda entry: (entry["class_name"], entry["sha256"]))
    INVENTORY.write_text(json.dumps(inventory, indent=2) + "\n")
    FIXTURES.write_text(json.dumps(fixtures, indent=2) + "\n")
    print(f"Inventoried {len(tags)} release tags, {len(entries)} fingerprints, {len(fixtures)} distinct fixtures")


if __name__ == "__main__":
    main()
