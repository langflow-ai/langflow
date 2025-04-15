from ._import_from_source import _test_imports_from_source, _recurse_modules

def test_components_imports():
    """Test imports for all files under langflow.components"""
    # Get all modules under components
    modules = list(_recurse_modules(
        "langflow.components", 
        ignore_tests=True, 
        packages_only=False
    ))
    
    # Run the strict import check on each module
    for module in modules:
        _test_imports_from_source(module)
