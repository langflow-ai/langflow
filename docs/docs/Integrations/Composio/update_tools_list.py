"""Update the Composio tools list in the integrations-composio.mdx file."""

import re
from pathlib import Path

# Scan for tools
composio_dir = Path("../../../../src/backend/base/langflow/components/composio")
tools = []

for file_path in composio_dir.glob("*.py"):
    if file_path.name in ["__init__.py", "composio_api.py"]:
        continue

    with file_path.open() as f:
        content = f.read()
        match = re.search(r'display_name:\s*str\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            tools.append(match.group(1))

# Update MDX file
tools.sort()
mdx_file = Path("integrations-composio.mdx")

with mdx_file.open() as f:
    content = f.read()

# Create the tools list content
tools_list = "## Available Composio tools\n\n" + "\n".join(f"- **{tool}**" for tool in tools) + "\n"

# Replace the existing "Available Composio tools" section with the new one
pattern = r"## Available Composio tools\n\n.*?(?=\n## |$)"
new_content = re.sub(pattern, tools_list, content, flags=re.DOTALL)

with mdx_file.open("w") as f:
    f.write(new_content)
