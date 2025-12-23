#!/usr/bin/env python3
"""Build documentation bundle for Langflow Flow Assistant.

This script processes MDX documentation files and creates a JSON bundle
that can be included in the Langflow backend package.

Usage:
    python scripts/build_agent_docs.py

The output file is saved to:
    src/backend/base/langflow/initial_setup/agent_docs.json
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DOCS_ROOT = PROJECT_ROOT / "docs" / "docs"
OUTPUT_FILE = PROJECT_ROOT / "src" / "backend" / "base" / "langflow" / "initial_setup" / "agent_docs.json"

# Constants
FRONTMATTER_PARTS_COUNT = 3
MIN_PARAGRAPH_LENGTH = 20
MAX_KEYWORDS = 20
SUMMARY_MAX_LENGTH = 300


@dataclass
class DocumentationPage:
    """Represents a single documentation page."""

    title: str
    slug: str
    category: str
    content: str
    summary: str = ""
    keywords: list[str] = field(default_factory=list)


def extract_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter from MDX content."""
    frontmatter: dict[str, str] = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= FRONTMATTER_PARTS_COUNT:
            fm_content = parts[1].strip()
            body = parts[2].strip()

            for line in fm_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    return frontmatter, body


def clean_mdx_content(content: str) -> str:
    """Clean MDX content by removing imports, JSX components, and formatting."""
    # Remove import statements
    content = re.sub(r"^import\s+.*$", "", content, flags=re.MULTILINE)

    # Remove JSX components with self-closing tags
    content = re.sub(r"<[A-Z][a-zA-Z]*\s+[^>]*/>", "", content)

    # Remove JSX component blocks (e.g., <Tabs>...</Tabs>)
    content = re.sub(r"<[A-Z][a-zA-Z]*[^>]*>[\s\S]*?</[A-Z][a-zA-Z]*>", "", content)

    # Remove JSX inline components (e.g., <Icon name="..." />)
    content = re.sub(r"<Icon[^>]*>", "", content)
    content = re.sub(r"</Icon>", "", content)

    # Remove admonition markers but keep content
    content = re.sub(r":::(tip|info|warning|danger|note)\s*", "\n**Note:** ", content)
    content = re.sub(r":::", "", content)

    # Remove HTML comments
    content = re.sub(r"<!--[\s\S]*?-->", "", content)

    # Clean up excessive whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def extract_summary(content: str, max_length: int = SUMMARY_MAX_LENGTH) -> str:
    """Extract a summary from the content (first paragraph or first N chars)."""
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    for para in paragraphs:
        # Skip headers and code blocks
        if para.startswith(("#", "```")):
            continue
        # Skip short lines
        if len(para) < MIN_PARAGRAPH_LENGTH:
            continue

        # Clean and truncate
        summary = para[:max_length]
        if len(para) > max_length:
            summary = summary.rsplit(" ", 1)[0] + "..."
        return summary

    return ""


def extract_keywords(content: str, title: str) -> list[str]:
    """Extract keywords from content for search indexing."""
    keywords: set[str] = set()

    # Add words from title
    title_words = re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())
    keywords.update(title_words)

    # Extract words from headers
    headers = re.findall(r"^#{1,6}\s+(.+)$", content, re.MULTILINE)
    for header in headers:
        header_words = re.findall(r"\b[a-zA-Z]{3,}\b", header.lower())
        keywords.update(header_words)

    # Extract emphasized terms
    bold_terms = re.findall(r"\*\*([^*]+)\*\*", content)
    for term in bold_terms:
        term_words = re.findall(r"\b[a-zA-Z]{3,}\b", term.lower())
        keywords.update(term_words)

    # Common stop words to exclude
    stop_words = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "are",
        "from",
        "can",
        "you",
        "your",
        "have",
        "will",
        "when",
        "how",
        "what",
        "use",
        "using",
        "more",
        "see",
        "also",
        "example",
        "following",
        "information",
        "about",
        "other",
    }
    keywords -= stop_words

    return sorted(keywords)[:MAX_KEYWORDS]


def get_category_from_path(path: Path) -> str:
    """Determine category from file path."""
    relative = path.relative_to(DOCS_ROOT)
    parts = relative.parts

    if len(parts) > 1:
        return parts[0].lower().replace("-", "_")
    return "general"


def process_mdx_file(path: Path) -> DocumentationPage | None:
    """Process a single MDX file into a DocumentationPage."""
    try:
        content = path.read_text(encoding="utf-8")
        frontmatter, body = extract_frontmatter(content)

        title = frontmatter.get("title", path.stem.replace("-", " ").title())
        slug = frontmatter.get("slug", f"/{path.stem}")
        category = get_category_from_path(path)

        clean_content = clean_mdx_content(body)
        summary = extract_summary(clean_content)
        keywords = extract_keywords(clean_content, title)

        return DocumentationPage(
            title=title,
            slug=slug,
            category=category,
            content=clean_content,
            summary=summary,
            keywords=keywords,
        )
    except (OSError, ValueError, KeyError) as e:
        print(f"  Warning: Failed to process {path}: {e}", file=sys.stderr)
        return None


def build_documentation_bundle() -> dict:
    """Build the complete documentation bundle."""
    if not DOCS_ROOT.exists():
        print(f"Error: Documentation root not found: {DOCS_ROOT}", file=sys.stderr)
        sys.exit(1)

    pages: dict[str, dict] = {}
    categories: dict[str, list[str]] = {}

    mdx_files = list(DOCS_ROOT.rglob("*.mdx"))
    print(f"Found {len(mdx_files)} MDX files in {DOCS_ROOT}")

    processed = 0
    skipped = 0

    for mdx_file in sorted(mdx_files):
        # Skip partial files (they are included in other files)
        if mdx_file.name.startswith("_partial"):
            skipped += 1
            continue

        page = process_mdx_file(mdx_file)
        if page:
            # Store by slug (primary key)
            pages[page.slug] = asdict(page)

            # Also index by filename for convenience
            filename_key = mdx_file.stem
            if filename_key not in pages:
                pages[filename_key] = asdict(page)

            # Build category index
            if page.category not in categories:
                categories[page.category] = []
            if page.slug not in categories[page.category]:
                categories[page.category].append(page.slug)

            processed += 1
        else:
            skipped += 1

    print(f"Processed: {processed}, Skipped: {skipped}")

    # Sort categories
    for slugs_list in categories.values():
        slugs_list.sort()

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_pages": processed,
        "categories": categories,
        "pages": pages,
    }


def main():
    """Main entry point."""
    print("Building Langflow Agent Documentation Bundle...")
    print(f"Source: {DOCS_ROOT}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    bundle = build_documentation_bundle()

    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON bundle
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)

    file_size = OUTPUT_FILE.stat().st_size
    print()
    print(f"Successfully created: {OUTPUT_FILE}")
    print(f"File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    print(f"Categories: {len(bundle['categories'])}")
    print(f"Total pages: {bundle['total_pages']}")

    # Print category summary
    print("\nCategories:")
    for category, slugs in sorted(bundle["categories"].items()):
        print(f"  {category}: {len(slugs)} pages")


if __name__ == "__main__":
    main()
