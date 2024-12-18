# Testing Langflow Components Guide

This guide explains how to test and run Langflow components directly in code, without needing the Langflow UI. We'll cover both using the generic component tester and writing custom test scripts.

## Table of Contents
1. [Using the Component Tester](#using-the-component-tester)
2. [Testing Specific Components](#testing-specific-components)
3. [Environment Setup](#environment-setup)
4. [Best Practices](#best-practices)
5. [Troubleshooting](#troubleshooting)

## Using the Component Tester

The `ComponentTester` class provides a generic way to test any Langflow component. Here's how to use it:

```python
from component_tester import OpenAITester

# Create a tester instance
tester = OpenAITester()

# Test with default parameters
tester.test_with_parameters()

# Test with custom parameters
custom_params = {
    "model_name": "gpt-3.5-turbo",
    "temperature": 0.9,
    "max_tokens": 150
}
tester.test_with_parameters(custom_params)
```

### Features
- Automatic environment variable loading
- Parameter validation
- Configuration display
- Error handling
- JSON mode support
- Response formatting

## Testing Specific Components

### OpenAI Component Example
Here's a complete example of testing the OpenAI component:

```python
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Load environment variables
repo_root = Path(__file__).parent.parent
load_dotenv(repo_root / ".env")

# Initialize the model
params = {
    "model_name": "gpt-3.5-turbo",
    "temperature": 0.7,
    "max_tokens": 100,
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "presence_penalty": 0.5,
    "seed": 42
}

# Create and test the model
model = ChatOpenAI(**params)
response = model.invoke("Tell me a joke")
print(response.content)
```

### Custom Component Testing Template
Here's a template for testing any Langflow component:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
repo_root = Path(__file__).parent.parent
load_dotenv(repo_root / ".env")

class ComponentTester:
    def __init__(self, component_class):
        self.component = component_class()

    def set_parameters(self, params):
        for name, value in params.items():
            setattr(self.component, name, value)

    def test(self, test_input):
        try:
            model = self.component.build()
            return model.invoke(test_input)
        except Exception as e:
            print(f"Error: {str(e)}")
            raise

# Usage example:
# tester = ComponentTester(YourComponent)
# tester.set_parameters(your_params)
# result = tester.test("Your test input")
```

## Environment Setup

1. **Directory Structure**
   ```
   langflow/
   ├── felipe/
   │   ├── component_tester.py
   │   ├── test_openai_component_manual.py
   │   └── your_test_script.py
   ├── .env
   └── requirements.txt
   ```

2. **Environment Variables**
   Create a `.env` file in the root directory:
   ```
   OPENAI_API_KEY=your_api_key_here
   OTHER_API_KEY=other_api_key_here
   ```

3. **Dependencies**
   Required packages:
   ```
   python-dotenv
   langchain
   langchain-openai
   ```

## Best Practices

1. **API Key Management**
   - Always use environment variables for API keys
   - Never hardcode sensitive information
   - Use SecretStr for API key parameters

2. **Error Handling**
   ```python
   try:
       model = component.build()
       response = model.invoke(prompt)
   except Exception as e:
       print(f"Error: {str(e)}")
       # Handle specific exceptions
   ```

3. **Parameter Validation**
   ```python
   def validate_params(params):
       required = ["model_name", "temperature"]
       missing = [p for p in required if p not in params]
       if missing:
           raise ValueError(f"Missing required parameters: {missing}")
   ```

4. **Testing Different Scenarios**
   ```python
   # Test with minimal parameters
   tester.test_with_parameters({"model_name": "gpt-3.5-turbo"})

   # Test with full parameters
   tester.test_with_parameters(full_params)

   # Test error cases
   tester.test_with_parameters({"invalid_param": "value"})
   ```

## Troubleshooting

### Common Issues and Solutions

1. **ImportError: Module not found**
   - Check your Python path
   - Verify package installation
   - Use absolute imports

2. **API Key Errors**
   - Verify .env file location
   - Check environment variable names
   - Ensure proper loading of .env file

3. **Component Build Errors**
   - Verify required parameters
   - Check parameter types
   - Review component documentation

4. **Circular Import Issues**
   - Use lazy imports
   - Restructure imports
   - Import from specific modules

### Debug Tips

1. **Enable Verbose Logging**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Print Component State**
   ```python
   def print_component_state(component):
       for attr in dir(component):
           if not attr.startswith('_'):
               print(f"{attr}: {getattr(component, attr)}")
   ```

3. **Test Parameter Sets**
   ```python
   test_sets = [
       {"name": "minimal", "params": {"model_name": "gpt-3.5-turbo"}},
       {"name": "full", "params": full_params},
       {"name": "error", "params": {"invalid": "params"}}
   ]

   for test in test_sets:
       print(f"\nRunning {test['name']} test:")
       try:
           tester.test_with_parameters(test['params'])
       except Exception as e:
           print(f"Expected error for {test['name']}: {e}")
   ```

## Conclusion

Testing components directly in code provides more control and flexibility than using the UI. The provided tools and templates make it easy to:
- Develop and test new components
- Debug existing components
- Automate testing scenarios
- Integrate components into other applications

For more examples and component-specific guides, refer to the other documentation files in this directory.
