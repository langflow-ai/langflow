---
title: Contribute components
slug: /contributing-components
---


New components are added as objects of the [CustomComponent](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/custom/custom_component/custom_component.py) class.

Any dependencies are added to the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/main/pyproject.toml#L148) file.

### Contribute an example component to Langflow

Anyone can contribute an example component. For example, if you created a new document loader called **MyCustomDocumentLoader**, you can follow these steps to contribute it to Langflow.

1. Write your loader as an object of the [CustomComponent](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/custom/custom_component/custom_component.py) class. You'll create a new class, `MyCustomDocumentLoader`, that will inherit from `CustomComponent` and override the base class's methods.
2. Define optional attributes like `display_name`, `description`, and `documentation` to provide information about your custom component.
3. Implement the `build_config` method to define the configuration options for your custom component.
4. Implement the `build` method to define the logic for taking input parameters specified in the `build_config` method and returning the desired output.
5. Add the code to the [/components/documentloaders](https://github.com/langflow-ai/langflow/tree/dev/src/backend/base/langflow/components) folder.
6. Add the dependency to [/documentloaders/__init__.py](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/components/documentloaders/__init__.py) as `from .MyCustomDocumentLoader import MyCustomDocumentLoader`.
7. Add any new dependencies to the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/main/pyproject.toml#L148) file.
8. Submit documentation for your component. For this example, you'd submit documentation to the [loaders page](https://github.com/langflow-ai/langflow/blob/main/docs/docs/Components/components-loaders.md).
9. Submit your changes as a pull request. The Langflow team will have a look, suggest changes, and add your component to Langflow.