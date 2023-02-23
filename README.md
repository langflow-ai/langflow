<!-- Title -->

# LangFlow

A no-code flow builder for langchain

<p>
<img alt="GitHub Contributors" src="https://img.shields.io/github/contributors/logspace-ai/langflow" />
<img alt="GitHub Last Commit" src="https://img.shields.io/github/last-commit/logspace-ai/langflow" />
<!-- <img alt="GitHub Language Count" src="https://img.shields.io/github/languages/count/logspace-ai/langflow" /> -->
<img alt="" src="https://img.shields.io/github/repo-size/logspace-ai/langflow" />
<!-- <img alt="GitHub Issues" src="https://img.shields.io/github/issues/logspace-ai/langflow" /> -->
<!-- <img alt="GitHub Closed Issues" src="https://img.shields.io/github/issues-closed/logspace-ai/langflow" /> -->
<!-- <img alt="GitHub Pull Requests" src="https://img.shields.io/github/issues-pr/logspace-ai/langflow" /> -->
<!-- <img alt="GitHub Closed Pull Requests" src="https://img.shields.io/github/issues-pr-closed/logspace-ai/langflow" />  -->
<!-- <img alt="GitHub Commit Activity (Year)" src="https://img.shields.io/github/commit-activity/y/logspace-ai/langflow" /> -->
<img alt="Github License" src="https://img.shields.io/github/license/logspace-ai/langflow" />  
</p>

![LangFlow Logo](https://github.com/logspace-ai/langflow/blob/main/img/llm_simple_flow.png)

LangFlow is a no-code flow maker for LangChain, designed to provide an intuitive interface for building custom AI pipelines. With LangFlow, users can easily create custom flows using a drag-and-drop interface, combining the capabilities of LangChain with external tools.

## 📦 Installation

To get started with LangFlow, you first need to install the LangChain library. You can do this using the following command:

`pip install langchain`

You can also install LangFlow via pip:

`pip install langflow`

Next, set the `OPENAI_API_KEY` environment variable using one of the following methods:

- Use the following command in your terminal: `export OPENAI_API_KEY=your-api-key`.
- In a Python script or Jupyter notebook, use the following code: `import os; os.environ["OPENAI_API_KEY"] = "your-api-key"`.

## 🎨 Creating Flows

Creating flows with LangFlow is easy, thanks to its intuitive drag-and-drop interface. Simply drag components from the sidebar onto the canvas, and connect them together to create your custom NLP pipeline. LangFlow provides a range of pre-built components to choose from, including LLMs, prompt serializers, document loaders, and more.

## 💻 Examples

LangFlow comes with a number of example flows to help you get started. These examples cover a range of use cases, from chatbots and question-answering systems to data augmentation and model comparison. You can use these examples as a starting point for your own custom flows, or modify them to suit your needs.

## 🧰 Components

LangFlow provides support for LangChain main components, including prompts, LLMs, document loaders, utils, chains, indexes, agents, and memory. For each module, we provide examples to get started, how-to guides, reference docs, and conceptual guides.

For more information on each component, please refer to the [Modules section of the LangChain documentation](https://langchain-docs.example.com/modules).

## 🔧 Contributing

We welcome contributions to LangFlow! If you'd like to contribute, please follow our contributing guidelines. You can also get in touch with us via GitHub issues or our community forum.

## 📄 License

LangFlow is released under the MIT License. See the LICENSE file for details.
