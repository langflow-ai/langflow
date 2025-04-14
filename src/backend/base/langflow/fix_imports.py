import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple, DefaultDict
from collections import defaultdict
from datetime import datetime

class ImportFixer:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.package_name = "langflow"
        # Map of symbol to its defining module
        self.symbol_definitions: Dict[str, str] = {}
        print(f"Initialized ImportFixer with root directory: {self.root_dir}")
        self._find_symbol_definitions()

    def _find_symbol_definitions(self):
        """Find the actual module where each symbol is defined."""
        print("Finding symbol definitions...")
        
        # Track all valid locations for each symbol
        self.valid_symbol_locations = defaultdict(set)
        
        for py_file in self.root_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                relative_path = py_file.parent.relative_to(self.root_dir)
                module_parts = [self.package_name] + list(relative_path.parts) + [py_file.stem]
                module_path = ".".join(module_parts)

                # Look for actual definitions
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                        self.valid_symbol_locations[node.name].add(module_path)

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

        # Debug output
        print("\nSymbol locations:")
        for symbol, locations in sorted(self.valid_symbol_locations.items()):
            if len(locations) > 1:
                print(f"{symbol}: {sorted(locations)}")

    def _should_fix_import(self, node: ast.ImportFrom, file_path: Path) -> bool:
        """Determine if an import should be fixed."""
        if file_path.name == "__init__.py":
            return False
    
        if not node.module or not node.module.startswith('langflow.'):
            return False
    
        # Only fix imports that are using a parent path when the symbol
        # is actually defined in a child module
        for name in node.names:
            if name.name in self.valid_symbol_locations:
                locations = self.valid_symbol_locations[name.name]
                
                # If current module contains the definition, don't change it
                if node.module in locations:
                    return False
                
                # If current module is a parent of any location that contains
                # the definition, we might need to fix it
                for location in locations:
                    if location.startswith(node.module + "."):
                        # But only if there's exactly one child module with the definition
                        child_modules = [loc for loc in locations if loc.startswith(node.module + ".")]
                        if len(child_modules) == 1:
                            return True

        return False

    def _fix_imports_in_content(self, content: str, file_path: Path) -> str:
        """Fix imports in the given content."""
        tree = ast.parse(content)
        lines = content.split('\n')
        new_lines = lines.copy()
        offset = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and self._should_fix_import(node, file_path):
                # Group imports by their target modules
                imports_by_module = defaultdict(list)
                
                for name in node.names:
                    if name.name in self.valid_symbol_locations:
                        locations = self.valid_symbol_locations[name.name]
                        # Find the child module that contains the definition
                        child_modules = [loc for loc in locations if loc.startswith(node.module + ".")]
                        if len(child_modules) == 1:
                            imports_by_module[child_modules[0]].append(name.name)
                        else:
                            # Keep original module if we can't determine a single target
                            imports_by_module[node.module].append(name.name)
                    else:
                        # Keep original module for unknown symbols
                        imports_by_module[node.module].append(name.name)

                # Generate new import statements
                original_line = lines[node.lineno - 1]
                indentation = len(original_line) - len(original_line.lstrip())
                indent = original_line[:indentation]
                
                new_imports = []
                for module, symbols in imports_by_module.items():
                    symbols_str = ", ".join(sorted(symbols))
                    new_imports.append(f"{indent}from {module} import {symbols_str}")

                # Replace the original line with new imports
                if new_imports:
                    new_lines[node.lineno - 1 + offset] = new_imports[0]
                    if len(new_imports) > 1:
                        for i, new_import in enumerate(new_imports[1:], 1):
                            new_lines.insert(node.lineno - 1 + offset + i, new_import)
                            offset += 1

        return '\n'.join(new_lines)

    def fix_imports(self):
        """Fix imports to point to defining modules."""
        print("\nFixing imports...")
        files_processed = 0
        files_modified = 0
        
        for py_file in self.root_dir.rglob("*.py"):
            files_processed += 1
            
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    original_content = content

                if "from langflow." in content:  # Quick check before parsing
                    fixed_content = self._fix_imports_in_content(content, py_file)

                    if fixed_content != original_content:
                        print(f"\nModifying {py_file}")
                        print("Original:", original_content.splitlines()[0])
                        print("Fixed:", fixed_content.splitlines()[0])
                        with open(py_file, 'w') as f:
                            f.write(fixed_content)
                        files_modified += 1

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

        print(f"\nProcessed {files_processed} files, modified {files_modified} files")

def main():
    # Get the current directory
    current_dir = Path.cwd()
    print(f"Current working directory: {current_dir}")
    
    fixer = ImportFixer(current_dir)
    fixer.fix_imports()

if __name__ == "__main__":
    main()
