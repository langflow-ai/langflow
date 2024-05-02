# How to contribute components?

As of Langflow 1.0 alpha, new components are added as objects of the `CustomComponent` class and any dependencies are added to the pyproject.toml file.

## Add an example component

You have a new document loader called **MyCustomEmbedding** and it would look awesome in Langflow.

1. Write your loader as an object of the [CustomComponent](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/interface/custom/custom_component/custom_component.py) class. You'll create a new class, `MyCustomEmbeddingComponent`, that will inherit from `CustomComponent` and override the base class's methods.
2. Define optional attributes like `display_name`, `description`, and `documentation` to provide information about your custom component.
3. Implement the `build_config` method to define the configuration options for your custom component.
4. Implement the `build` method to define the logic for taking input parameters specified in the `build_config` method and returning the desired output.
5. Add the code to the [/components/document_loaders](https://github.com/langflow-ai/langflow/tree/dev/src/backend/base/langflow/components) folder.
6. Add the dependency to [/document_loaders/\_\_init\_\_.py](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/components/documentloaders/__init__.py) as `from .MyCustomEmbedding import MyCustomEmbeddingComponent`.
7. Add any new dependencies to the outer [pyproject.toml](https://github.com/langflow-ai/langflow/blob/dev/pyproject.toml#L27) file.
8. Submit your changes as a pull request. The Langflow team will have a look, suggest changes, and add your component to Langflow.




