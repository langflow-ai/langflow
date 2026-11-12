# ruff: noqa: INP001
"""Refresh the bundle-list tables from the package metadata.

Default packages come from the ``langflow-extensions:bundle-deps`` block in
the root ``pyproject.toml``. Opt-in standalone packages are the other
``src/bundles/lfx-*`` projects. The ``lfx-bundles`` table is the metapackage
extras, minus retired extras and packages that already have their own
``lfx-*`` distribution.

    uv run python docs/scripts/generate_bundle_list.py
    uv run python docs/scripts/generate_bundle_list.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_LIST = REPO_ROOT / "docs" / "docs" / "Lfx" / "extensions-bundle-list.mdx"
OPT_IN_PARTIAL = REPO_ROOT / "docs" / "docs" / "_partial-opt-in-bundles.mdx"
COMPONENTS = REPO_ROOT / "docs" / "docs" / "Components"
LANGFLOW_PROJECT = REPO_ROOT / "pyproject.toml"
BUNDLES_DIR = REPO_ROOT / "src" / "bundles"
METAPACKAGE = BUNDLES_DIR / "lfx-bundles" / "pyproject.toml"

DEPS_START = "# langflow-extensions:bundle-deps-start"
DEPS_END = "# langflow-extensions:bundle-deps-end"
RETIRED = frozenset({"altk", "chroma"})
PAGE_FOR_BUNDLE = {
    "litellm": "bundles-lite-llm.mdx",
    "mistral": "bundles-mistralai.mdx",
    "toolguard": "policies.mdx",
}
INSTALL_SUFFIX = {
    "codeagents": ", then [manually install OpenDsStar](./bundles-codeagents#prerequisites)",
}
TITLE_SUFFIXES = (" components", " integration", " (Beta)")


def _marked(name: str) -> tuple[str, str]:
    return f"{{/* bundle-list:{name} */}}", f"{{/* /bundle-list:{name} */}}"


def _replace_marked(text: str, name: str, body: str) -> str:
    start, end = _marked(name)
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    replacement = f"{start}\n{body.rstrip()}\n{end}"
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        message = f"Bundle list is missing the {name} markers."
        raise RuntimeError(message)
    return updated


def _langflow_version(project_text: str) -> str:
    match = re.search(r'(?m)^version = "([^"]+)"', project_text)
    if match is None:
        message = "Root pyproject.toml has no project version."
        raise RuntimeError(message)
    return ".".join(match.group(1).split(".")[:2])


def default_packages(project_text: str) -> list[str]:
    """Return bundle ids installed with ``uv pip install langflow``."""
    try:
        block = project_text.split(DEPS_START, 1)[1].split(DEPS_END, 1)[0]
    except IndexError as exc:
        message = "Root pyproject.toml is missing the bundle-deps markers."
        raise RuntimeError(message) from exc
    names = re.findall(r'"lfx-([a-z0-9-]+)', block)
    return sorted(set(names))


def standalone_packages() -> set[str]:
    """Return bundle ids that ship as their own ``lfx-*`` project."""
    names: set[str] = set()
    for project in BUNDLES_DIR.glob("*/pyproject.toml"):
        if project.parent.name == "lfx-bundles":
            continue
        with project.open("rb") as handle:
            package_name = tomllib.load(handle)["project"]["name"]
        if package_name.startswith("lfx-"):
            names.add(package_name.removeprefix("lfx-"))
    return names


def metapackage_packages(standalone: set[str]) -> list[str]:
    """Return extras that are still installed through ``lfx-bundles``."""
    with METAPACKAGE.open("rb") as handle:
        extras = tomllib.load(handle)["project"]["optional-dependencies"]
    skipped = {"all", "all-no-torch"} | RETIRED | standalone
    return sorted(name for name in extras if name not in skipped)


def _page_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"')
            for suffix in TITLE_SUFFIXES:
                title = title.removesuffix(suffix)
            return title
    return path.stem


def _bundle_cell(bundle: str, *, command: str) -> str:
    filename = PAGE_FOR_BUNDLE.get(bundle, f"bundles-{bundle}.mdx")
    page = COMPONENTS / filename
    install = f"`{command}`{INSTALL_SUFFIX.get(bundle, '')}"
    if not page.is_file():
        return f"| `{bundle}` | {install} |"
    slug = f"/bundles-{bundle}"
    for line in page.read_text(encoding="utf-8").splitlines():
        if line.startswith("slug:"):
            slug = line.split(":", 1)[1].strip()
            break
    label = _page_title(page)
    href = f".{slug}" if slug.startswith("/") else f"./{slug}"
    return f"| [`{bundle}`]({href}) ({label}) | {install} |"


def _table(rows: list[str]) -> str:
    header = "| Bundle | Install command |\n| --- | --- |"
    return header + "\n" + "\n".join(rows)


def render_tables() -> dict[str, str]:
    """Build the three generated regions of the bundle list."""
    project_text = LANGFLOW_PROJECT.read_text(encoding="utf-8")
    included = default_packages(project_text)
    standalone = standalone_packages()
    opt_in = sorted(standalone - set(included))
    metapackage = metapackage_packages(standalone)
    version = _langflow_version(project_text)
    return {
        "version": f"This list reflects the bundles included with Langflow {version}.",
        "default": _table([_bundle_cell(name, command=f"uv pip install lfx-{name}") for name in included]),
        "opt-in-standalone": _table([_bundle_cell(name, command=f"uv pip install lfx-{name}") for name in opt_in]),
        "metapackage": _table(
            [_bundle_cell(name, command=f'uv pip install "lfx-bundles[{name}]"') for name in metapackage]
        ),
    }


def _drop_graduated_names(partial: str, included: set[str]) -> str:
    updated = partial
    for name in sorted(included):
        updated = re.sub(rf" · \[`{re.escape(name)}`\]\([^)]*\)", "", updated)
        updated = re.sub(rf" · `{re.escape(name)}`", "", updated)
    return updated


def write_bundle_list(*, check: bool) -> list[str]:
    """Write the generated regions, or return the paths that differ."""
    regions = render_tables()
    list_text = BUNDLE_LIST.read_text(encoding="utf-8")
    for name, body in regions.items():
        list_text = _replace_marked(list_text, name, body)
    included = set(default_packages(LANGFLOW_PROJECT.read_text(encoding="utf-8")))
    partial_text = _drop_graduated_names(OPT_IN_PARTIAL.read_text(encoding="utf-8"), included)
    drifted: list[str] = []
    current_list = BUNDLE_LIST.read_text(encoding="utf-8")
    current_partial = OPT_IN_PARTIAL.read_text(encoding="utf-8")
    if list_text != current_list:
        drifted.append(str(BUNDLE_LIST.relative_to(REPO_ROOT)))
    if partial_text != current_partial:
        drifted.append(str(OPT_IN_PARTIAL.relative_to(REPO_ROOT)))
    if check or not drifted:
        return drifted
    BUNDLE_LIST.write_text(list_text, encoding="utf-8")
    OPT_IN_PARTIAL.write_text(partial_text, encoding="utf-8")
    return []


def main(argv: list[str] | None = None) -> int:
    """Generate the bundle list, or fail when ``--check`` finds drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when the bundle list differs")
    args = parser.parse_args(argv)
    try:
        drifted = write_bundle_list(check=args.check)
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if drifted:
        sys.stderr.write("Bundle list docs are out of date:\n")
        sys.stderr.write("\n".join(f"  {path}" for path in drifted) + "\n")
        sys.stderr.write("Run: uv run python docs/scripts/generate_bundle_list.py\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
