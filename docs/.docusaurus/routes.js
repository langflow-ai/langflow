import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/langflow/markdown-page',
    component: ComponentCreator('/langflow/markdown-page', '677'),
    exact: true
  },
  {
    path: '/langflow/',
    component: ComponentCreator('/langflow/', 'af1'),
    routes: [
      {
        path: '/langflow/',
        component: ComponentCreator('/langflow/', '337'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/buffer-memory',
        component: ComponentCreator('/langflow/buffer-memory', '497'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/collection',
        component: ComponentCreator('/langflow/collection', 'daa'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/community',
        component: ComponentCreator('/langflow/community', '557'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/components',
        component: ComponentCreator('/langflow/components', '8e9'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/conversation-chain',
        component: ComponentCreator('/langflow/conversation-chain', 'c58'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/creating-flows',
        component: ComponentCreator('/langflow/creating-flows', '27b'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/csv-loader',
        component: ComponentCreator('/langflow/csv-loader', '8bc'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/features',
        component: ComponentCreator('/langflow/features', 'f1f'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/gcp-deployment',
        component: ComponentCreator('/langflow/gcp-deployment', 'f91'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/github-issues',
        component: ComponentCreator('/langflow/github-issues', '156'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/how-contribute',
        component: ComponentCreator('/langflow/how-contribute', 'd46'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/how-upload-examples',
        component: ComponentCreator('/langflow/how-upload-examples', '0fa'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/hugging-face-spaces',
        component: ComponentCreator('/langflow/hugging-face-spaces', 'e51'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/installation',
        component: ComponentCreator('/langflow/installation', '583'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/jina-deployment',
        component: ComponentCreator('/langflow/jina-deployment', 'ece'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/midjourney-prompt-chain',
        component: ComponentCreator('/langflow/midjourney-prompt-chain', '878'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/multiple-vectorstores',
        component: ComponentCreator('/langflow/multiple-vectorstores', 'ece'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/python-function',
        component: ComponentCreator('/langflow/python-function', 'a07'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/langflow/serp-api-tool',
        component: ComponentCreator('/langflow/serp-api-tool', 'fb8'),
        exact: true,
        sidebar: "docs"
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
