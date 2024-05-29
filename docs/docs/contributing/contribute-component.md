import ZoomableImage from "/src/theme/ZoomableImage.js";

# How to Contribute Components?

As of Langflow 1.0 alpha, new components are added as objects of the [CustomComponent](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/interface/custom/custom_component/custom_component.py) class and any dependencies are added to the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/dev/pyproject.toml#L27) file.

## Add an example component

You have a new document loader called **MyCustomDocumentLoader** and it would look awesome in Langflow.

1. Write your loader as an object of the [CustomComponent](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/interface/custom/custom_component/custom_component.py) class. You'll create a new class, `MyCustomDocumentLoader`, that will inherit from `CustomComponent` and override the base class's methods.
2. Define optional attributes like `display_name`, `description`, and `documentation` to provide information about your custom component.
3. Implement the `build_config` method to define the configuration options for your custom component.
4. Implement the `build` method to define the logic for taking input parameters specified in the `build_config` method and returning the desired output.
5. Add the code to the [/components/documentloaders](https://github.com/langflow-ai/langflow/tree/dev/src/backend/base/langflow/components) folder.
6. Add the dependency to [/documentloaders/\_\_init\_\_.py](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/components/documentloaders/__init__.py) as `from .MyCustomDocumentLoader import MyCustomDocumentLoader`.
7. Add any new dependencies to the outer [pyproject.toml](https://github.com/langflow-ai/langflow/blob/dev/pyproject.toml#L27) file.
8. Submit documentation for your component. For this example, you'd submit documentation to the [loaders page](https://github.com/langflow-ai/langflow/blob/dev/docs/docs/components/loaders.mdx).
9. Submit your changes as a pull request. The Langflow team will have a look, suggest changes, and add your component to Langflow.

## User Sharing

You might want to share and test your custom component with others, but don't need it merged into the main source code.

If so, you can share your component on the Langflow store.

1. [Register at the Langflow store](https://www.langflow.store/login/).
2. Undergo pre-validation before receiving an API key.
3. To deploy your amazing component directly to the Langflow store, without it being merged into the main source code, navigate to your flow, and then click **Share**.
   The share window appears:

<ZoomableImage
alt="Docusaurus themed image"
sources={{
    light: "img/add-component-to-store.png",
    dark: "img/add-component-to-store.png",
  }}
style={{ width: "50%", margin: "20px auto" }}
/>

5. Choose whether you want to flow to be public or private.
   You can also **Export** your flow as a JSON file from this window.
   When you're ready to share the flow, click **Share Flow**.
   You should see a **Flow shared successfully** popup.
6. To confirm, navigate to the **Langflow Store** and filter results by **Created By Me**. You should see your new flow on the **Langflow Store**.
