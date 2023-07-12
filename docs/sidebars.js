module.exports = {
  docs: [
    {
      type: "category",
      label: "Getting Started",
      collapsed: false,
      items: [
        "index",
        "getting-started/installation",
        "getting-started/hugging-face-spaces",
        "getting-started/creating-flows",
      ],
    },
    {
      type: "category",
      label: "Guidelines",
      collapsed: false,
      items: [
        "guidelines/components",
        "guidelines/features",
        "guidelines/collection",
      ],
    },
    {
      type: "category",
      label: "Examples",
      collapsed: false,
      items: [
        "examples/conversation-chain",
        "examples/buffer-memory",
        "examples/midjourney-prompt-chain",
        "examples/csv-loader",
        "examples/serp-api-tool",
        "examples/multiple-vectorstores",
        "examples/python-function",
        "examples/how-upload-examples",
      ],
    },
    {
      type: "category",
      label: "Deployment",
      collapsed: false,
      items: ["deployment/gcp-deployment", "deployment/jina-deployment"],
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
