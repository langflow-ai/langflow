"""Utility functions for starter projects operations."""

import json
import os
from pathlib import Path


def get_starter_projects_json_content():
    """Get the JSON content from all JSON files in the starter projects directory.
    
    This function reads JSON files directly from the filesystem without
    importing any modules to avoid dependency issues.
    
    Returns:
        list[dict]: List of JSON objects from the starter projects directory.
    """
    try:
        # Get the path to the starter projects directory
        backend_dir = Path(__file__).parent.parent
        starter_projects_dir = backend_dir / "initial_setup" / "starter_projects"
        
        json_contents = []
        
        if starter_projects_dir.exists() and starter_projects_dir.is_dir():
            # Only process JSON files, ignore Python files and __init__.py
            json_files = [f for f in starter_projects_dir.iterdir() 
                         if f.is_file() and f.suffix.lower() == '.json']
            
            # Sort files by name for consistent ordering
            json_files.sort(key=lambda x: x.name)
            
            for file_path in json_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_content = json.load(f)
                        json_contents.append(json_content)
                except (json.JSONDecodeError, IOError):
                    # Skip files that can't be read or aren't valid JSON
                    continue
        
        return json_contents
    except Exception:
        # Return empty list if there's any error accessing the directory
        return []
