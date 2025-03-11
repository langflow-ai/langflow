#!/usr/bin/env python3
# Run this script with the command `python3 scripts/get_package_versions.py`
#  to generate the luna-for-langflow.md file in the docs/docs/Support directory.
# It extracts the package versions from the uv.lock file and categorizes them.

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_uv_lock(file_path):
    """Parse uv.lock file using basic string operations."""
    with open(file_path) as f:
        content = f.read()

    # Extract Python version requirement
    python_version_match = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
    python_version = python_version_match.group(1) if python_version_match else "unknown"

    # Extract package versions
    packages = []
    package_blocks = re.finditer(r'\[\[package\]\]\s*name\s*=\s*"([^"]+)"\s*version\s*=\s*"([^"]+)"', content)
    for match in package_blocks:
        packages.append((match.group(1), match.group(2)))

    # Extract langflow version
    langflow_version = "unknown"
    for name, version in packages:
        if name == "langflow":
            langflow_version = version
            break

    return {"python_version": python_version, "langflow_version": langflow_version, "packages": packages}


def categorize_package(package_name):
    """Categorize packages based on their names."""
    categories = {
        "LangChain": ["langchain", "langchain-"],
        "Databases": [
            "redis",
            "mongo",
            "sql",
            "vector",
            "chromadb",
            "qdrant",
            "weaviate",
            "faiss",
            "elasticsearch",
            "pinecone",
            "milvus",
            "astradb",
            "cassio",
            "couchbase",
        ],
        "AI/ML": [
            "openai",
            "huggingface",
            "anthropic",
            "cohere",
            "mistral",
            "genai",
            "dspy",
            "litellm",
            "nvidia",
            "ollama",
            "groq",
            "vertexai",
        ],
        "Monitoring": ["langsmith", "langwatch", "langfuse", "arize", "phoenix"],
        "Utils": [
            "beautifulsoup4",
            "requests",
            "certifi",
            "pydantic",
            "fastapi",
            "httpx",
            "pytest",
            "mypy",
            "ruff",
            "black",
            "isort",
        ],
        "Integration": ["google-", "aws-", "azure-", "atlassian-", "github-", "gitlab-"],
    }

    for category, patterns in categories.items():
        if any(pattern in package_name.lower() for pattern in patterns):
            return category
    return "Other"


def get_package_versions(uv_lock_path):
    """Extract and categorize package versions from uv.lock."""
    lock_data = parse_uv_lock(uv_lock_path)

    # Categorize dependencies
    categorized_deps = defaultdict(list)
    for package_name, version in lock_data["packages"]:
        category = categorize_package(package_name)
        categorized_deps[category].append((package_name, version))

    return {
        "langflow_version": lock_data["langflow_version"],
        "python_version": lock_data["python_version"],
        "dependencies": dict(categorized_deps),
    }


def generate_markdown(versions_info):
    """Generate markdown content from version information."""
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Include frontmatter and introduction
    md_content = [
        "---",
        "title: Luna for Langflow",
        "slug: /luna-for-langflow",
        "---",
        "",
        "With [Luna for Langflow](https://www.datastax.com/products/luna-langflow) support, you can develop and deploy Langflow applications with confidence.",
        "",
        "**Luna** is a subscription to the Langflow expertise at DataStax. It's meant for users of Langflow who want all the benefits of running their own open-source deployments, but with the peace of mind that comes with having direct access to the team that has authored the majority of the Langflow code.",
        "",
        "**Luna** subscribers can get help with general-purpose and technical questions for their open-source Langflow deployments, and if an issue is encountered, DataStax is there to help.",
        "",
        "Ready to subscribe?",
        "",
        "Visit the [Luna for Langflow](https://www.datastax.com/products/luna-langflow) product page to get started.",
        "",
        "## Supported software",
        "",
        "Luna for Langflow support covers only the following software versions for Langflow.",
        "",
        "Last updated: " + current_date,
        "",
        "## Core information",
        "- **Langflow Version**: `" + versions_info["langflow_version"] + "`",
        "- **Python Version Required**: `" + versions_info["python_version"] + "`",
        "\n## Dependencies",
    ]

    # Add dependencies by category
    for category in sorted(versions_info["dependencies"].keys()):
        packages = versions_info["dependencies"][category]
        if packages:  # Only show categories with packages
            md_content.extend(["\n### " + category, "| Package | Version |", "| ------- | ------- |"])
            for package, version in sorted(packages):
                md_content.append("| " + package + " | `" + version + "` |")

    return "\n".join(md_content)


def main():
    uv_lock_path = Path(__file__).parent.parent / "uv.lock"
    output_path = Path(__file__).parent.parent / "docs/docs/Support/luna-for-langflow.md"

    if not uv_lock_path.exists():
        print(f"Error: Could not find uv.lock at {uv_lock_path}")
        return

    versions_info = get_package_versions(uv_lock_path)
    markdown_content = generate_markdown(versions_info)

    # Ensure the directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the markdown file
    with open(output_path, "w") as f:
        f.write(markdown_content)

    print(f"Markdown file generated at: {output_path}")


if __name__ == "__main__":
    main()
