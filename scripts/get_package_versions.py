#!/usr/bin/env python3

from pathlib import Path
from collections import defaultdict
import re
from datetime import datetime

def parse_toml(file_path):
    """Parse TOML file using basic string operations."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract version from project section
    version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
    project_version = version_match.group(1) if version_match else "unknown"
    
    # Extract Python version requirement
    python_version_match = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
    python_version = python_version_match.group(1) if python_version_match else "unknown"
    
    # Extract dependencies
    dependencies_start = content.find('dependencies = [')
    dependencies_end = content.find(']', dependencies_start)
    if dependencies_start != -1 and dependencies_end != -1:
        dependencies_content = content[dependencies_start:dependencies_end]
        dependencies = []
        for line in dependencies_content.split('\n'):
            if '=' in line and '"' in line:
                dep = line.strip().strip(',').strip('"')
                if dep:
                    dependencies.append(dep)
    else:
        dependencies = []
    
    # Extract optional dependencies from project.optional-dependencies section
    optional_deps = {}
    optional_section_start = content.find('[project.optional-dependencies]')
    if optional_section_start != -1:
        optional_section = content[optional_section_start:content.find('\n[', optional_section_start + 1)]
        sections = re.finditer(r'(\w+)\s*=\s*\[(.*?)\]', optional_section, re.DOTALL)
        for section in sections:
            env = section.group(1)
            deps = []
            for line in section.group(2).split('\n'):
                if '"' in line:
                    dep = line.strip().strip(',').strip('"')
                    if dep:
                        deps.append(dep)
            if deps:  # Only add sections that have dependencies
                optional_deps[env] = deps
    
    return {
        "project_version": project_version,
        "python_version": python_version,
        "dependencies": dependencies,
        "optional_dependencies": optional_deps
    }

def parse_version_info(version_spec):
    """Parse version specification into a more readable format."""
    # Remove any whitespace
    version_spec = version_spec.strip()
    
    # Handle simple version numbers
    if version_spec.startswith('"') or version_spec.startswith("'"):
        return version_spec.strip("'").strip('"')
    
    # Handle version ranges
    version_spec = version_spec.replace(">=", "≥").replace("<=", "≤").replace("~=", "≈")
    return version_spec

def categorize_package(package_name):
    """Categorize packages based on their names."""
    categories = {
        "LangChain": ["langchain", "langchain-"],
        "Databases": ["redis", "mongo", "sql", "vector", "chromadb", "qdrant", "weaviate", "faiss", 
                     "elasticsearch", "pinecone", "milvus", "astradb", "cassio", "couchbase"],
        "AI/ML": ["openai", "huggingface", "anthropic", "cohere", "mistral", "genai", "dspy", 
                 "litellm", "nvidia", "ollama", "groq", "vertexai"],
        "Monitoring": ["langsmith", "langwatch", "langfuse", "arize", "phoenix"],
        "Utils": ["beautifulsoup4", "requests", "certifi", "pydantic", "fastapi", "httpx",
                 "pytest", "mypy", "ruff", "black", "isort"],
        "Integration": ["google-", "aws-", "azure-", "atlassian-", "github-", "gitlab-"]
    }
    
    for category, patterns in categories.items():
        if any(pattern in package_name.lower() for pattern in patterns):
            return category
    return "Other"

def get_package_versions(pyproject_path):
    """Extract and categorize package versions from pyproject.toml."""
    toml_data = parse_toml(pyproject_path)
    
    # Categorize main dependencies
    categorized_deps = defaultdict(list)
    for dep in toml_data["dependencies"]:
        # Skip if it's a conditional dependency (like platform-specific)
        if ';' in dep:
            continue
            
        # Split package name and version spec
        if ">=" in dep or "<=" in dep or "==" in dep or "~=" in dep:
            package_name = re.split(r'>=|<=|==|~=', dep)[0]
            version_spec = dep[len(package_name):]
        else:
            package_name = dep
            version_spec = "any"
        
        category = categorize_package(package_name)
        categorized_deps[category].append((package_name, parse_version_info(version_spec)))
    
    return {
        "langflow_version": toml_data["project_version"],
        "python_version": toml_data["python_version"],
        "dependencies": dict(categorized_deps),
        "optional_dependencies": toml_data["optional_dependencies"]
    }

def generate_markdown(versions_info):
    """Generate markdown content from version information."""
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Include frontmatter and introduction
    md_content = [
        "---",
        "title: Supported software versions",
        "slug: /support-supported-software",
        "---",
        "",
        "Support covers only the following software versions for Langflow.",
        "",
        f"Last updated: {current_date}",
        "",
        "## Core Information",
        f"- **Langflow Version**: {versions_info['langflow_version']}",
        f"- **Python Version Required**: {versions_info['python_version']}",
        "\n## Main Dependencies",
    ]
    
    # Add main dependencies by category
    for category in sorted(versions_info['dependencies'].keys()):
        packages = versions_info['dependencies'][category]
        if packages:  # Only show categories with packages
            md_content.extend([
                f"\n### {category}",
                "| Package | Version |",
                "| ------- | ------- |"
            ])
            for package, version in sorted(packages):
                md_content.append(f"| {package} | {version} |")
    
    # Add optional dependencies
    if versions_info['optional_dependencies']:
        md_content.append("\n## Optional Dependencies")
        
        # Define the order of optional dependency sections
        optional_order = ['deploy', 'local', 'couchbase', 'cassio', 'postgresql']
        
        # First add the ordered sections
        for env in optional_order:
            if env in versions_info['optional_dependencies']:
                packages = versions_info['optional_dependencies'][env]
                if packages:  # Only show environments with packages
                    md_content.extend([
                        f"\n### {env}",
                        "| Package | Version |",
                        "| ------- | ------- |"
                    ])
                    for package in packages:
                        if ">=" in package or "<=" in package or "==" in package or "~=" in package:
                            package_name = re.split(r'>=|<=|==|~=', package)[0]
                            version_spec = package[len(package_name):]
                            md_content.append(f"| {package_name} | {parse_version_info(version_spec)} |")
                        else:
                            md_content.append(f"| {package} | any |")
        
        # Then add any remaining sections that aren't in the predefined order
        for env in sorted(set(versions_info['optional_dependencies'].keys()) - set(optional_order)):
            packages = versions_info['optional_dependencies'][env]
            if packages and not any(p.startswith(('src/', 'tests', '*/', 'io"', 'ALL', 'RUF', 'C90', 'pydantic')) for p in packages):
                md_content.extend([
                    f"\n### {env}",
                    "| Package | Version |",
                    "| ------- | ------- |"
                ])
                for package in packages:
                    if ">=" in package or "<=" in package or "==" in package or "~=" in package:
                        package_name = re.split(r'>=|<=|==|~=', package)[0]
                        version_spec = package[len(package_name):]
                        md_content.append(f"| {package_name} | {parse_version_info(version_spec)} |")
                    else:
                        md_content.append(f"| {package} | any |")
    
    return "\n".join(md_content)

def main():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    output_path = Path(__file__).parent.parent / "docs/docs/Support/supported-software.md"
    
    if not pyproject_path.exists():
        print(f"Error: Could not find pyproject.toml at {pyproject_path}")
        return
    
    versions_info = get_package_versions(pyproject_path)
    markdown_content = generate_markdown(versions_info)
    
    # Ensure the directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the markdown file
    with open(output_path, "w") as f:
        f.write(markdown_content)
    
    print(f"Markdown file generated at: {output_path}")

if __name__ == "__main__":
    main() 