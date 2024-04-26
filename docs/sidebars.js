module.exports = {
  docs: [
    {
      type: "category",
      label: " Getting Started",
      collapsed: false,
      items: [
        "index",
        "getting-started/install-langflow",
        "getting-started/quickstart",
        "getting-started/huggingface-spaces",
        "getting-started/new-to-llms",
      ],
    },

    {
      type: "category",
      label: " Starter Projects",
      collapsed: false,
      items: [
        "starter-projects/basic-prompting",
        "starter-projects/blog-writer",
        "starter-projects/document-qa",
        "starter-projects/memory-chatbot",
      ],
    },
    {
      type: "category",
      label: "Administration",
      collapsed: false,
      items: [
        "administration/login",
        "administration/api",
        "administration/cli",
        "administration/components",
        // "guidelines/features",
        "administration/collection",
        "administration/prompt-customization",
        "administration/langfuse_integration"
        // "guidelines/chat-interface",
        // "guidelines/chat-widget",
        // "guidelines/custom-component",
      ],
    },
    {
      type: "category",
      label: "Core Components",
      collapsed: false,
      items: [
        "components/inputs",
        "components/outputs",
        "components/data",
        "components/models",
        "components/helpers",
        "components/vector-stores",
        "components/embeddings",
        "components/custom",
      ],
    },
    {
      type: "category",
      label: "Extended Components",
      collapsed: true,
      items: [
        "components/agents",
        "components/chains",
        "components/experimental",
        "components/utilities",
        "components/model_specs",
        "components/retrievers",
        "components/text-splitters",
        "components/toolkits",
        "components/tools",
        // "components/memories",
      ],
    },

    {
      type: "category",
      label: "Example Components",
      collapsed: true,
      items: [
        "examples/flow-runner",
        "examples/conversation-chain",
        "examples/buffer-memory",
        "examples/csv-loader",
        "examples/searchapi-tool",
        "examples/serp-api-tool",
        "examples/python-function",
      ],
    },

    {
      type: "category",
      label: " Migration Guides",
      collapsed: false,
      items: [
        "migration/possible-installation-issues",
        "migration/migrating-to-one-point-zero",
        // "migration/flow-of-data",
        "migration/inputs-and-outputs",
        // "migration/supported-frameworks",
        // "migration/sidebar-and-interaction-panel",
        // "migration/new-categories-and-components",
        "migration/text-and-record",
        // "migration/custom-component",
        "migration/compatibility",
        // "migration/multiple-flows",
        // "migration/component-status-and-data-passing",
        // "migration/connecting-output-components",
        // "migration/renaming-and-editing-components",
        // "migration/passing-tweaks-and-inputs",
        "migration/global-variables",
        // "migration/experimental-components",
        // "migration/state-management",
        //"guides/rag-with-astradb",
      ],
    },

    {
      type: "category",
      label: "Tutorials",
      collapsed: true,
      items: [
        "tutorials/chatprompttemplate_guide",
        "tutorials/loading_document",
        "tutorials/rag-with-astradb",
      ],
    },

    {
      type: "category",
      label: "Deployment",
      collapsed: true,
      items: ["deployment/gcp-deployment"],
    },

    {
      type: "category",
      label: " What's New",
      collapsed: false,
      items: [
        "whats-new/a-new-chapter-langflow",
      ],
    },

    {
      type: "category",
      label: "Contributing",
      collapsed: false,
      items: [
        "contributing/how-contribute",
        "contributing/github-issues",
        "contributing/community",
      ],
    },
  ],
};
