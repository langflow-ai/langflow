import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/__docusaurus/debug',
    component: ComponentCreator('/__docusaurus/debug', '437'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/config',
    component: ComponentCreator('/__docusaurus/debug/config', 'f3c'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/content',
    component: ComponentCreator('/__docusaurus/debug/content', '5ed'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/globalData',
    component: ComponentCreator('/__docusaurus/debug/globalData', '6e2'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/metadata',
    component: ComponentCreator('/__docusaurus/debug/metadata', '00b'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/registry',
    component: ComponentCreator('/__docusaurus/debug/registry', '46d'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/routes',
    component: ComponentCreator('/__docusaurus/debug/routes', 'ce2'),
    exact: true
  },
  {
    path: '/markdown-page',
    component: ComponentCreator('/markdown-page', 'd68'),
    exact: true
  },
  {
    path: '/',
    component: ComponentCreator('/', '73a'),
    routes: [
      {
        path: '/',
        component: ComponentCreator('/', '08f'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/agents',
        component: ComponentCreator('/components/agents', '843'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/chains',
        component: ComponentCreator('/components/chains', '7ac'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/embeddings',
        component: ComponentCreator('/components/embeddings', '9c7'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/llms',
        component: ComponentCreator('/components/llms', 'ae5'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/loaders',
        component: ComponentCreator('/components/loaders', '80c'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/memories',
        component: ComponentCreator('/components/memories', '723'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/prompts',
        component: ComponentCreator('/components/prompts', '268'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/text-splitters',
        component: ComponentCreator('/components/text-splitters', '7f3'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/toolkits',
        component: ComponentCreator('/components/toolkits', 'b6c'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/tools',
        component: ComponentCreator('/components/tools', '960'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/utilities',
        component: ComponentCreator('/components/utilities', '24a'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/vector-stores',
        component: ComponentCreator('/components/vector-stores', 'bca'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components/wrappers',
        component: ComponentCreator('/components/wrappers', 'f16'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/contributing/community',
        component: ComponentCreator('/contributing/community', 'a0d'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/contributing/github-issues',
        component: ComponentCreator('/contributing/github-issues', 'bba'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/contributing/how-contribute',
        component: ComponentCreator('/contributing/how-contribute', '3f1'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/deployment/gcp-deployment',
        component: ComponentCreator('/deployment/gcp-deployment', '4f2'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/deployment/jina-deployment',
        component: ComponentCreator('/deployment/jina-deployment', 'def'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/buffer-memory',
        component: ComponentCreator('/examples/buffer-memory', 'b72'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/conversation-chain',
        component: ComponentCreator('/examples/conversation-chain', '0ce'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/csv-loader',
        component: ComponentCreator('/examples/csv-loader', '6f7'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/how-upload-examples',
        component: ComponentCreator('/examples/how-upload-examples', '274'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/midjourney-prompt-chain',
        component: ComponentCreator('/examples/midjourney-prompt-chain', 'a73'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/multiple-vectorstores',
        component: ComponentCreator('/examples/multiple-vectorstores', '7b0'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/python-function',
        component: ComponentCreator('/examples/python-function', '1d9'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/examples/serp-api-tool',
        component: ComponentCreator('/examples/serp-api-tool', '9d4'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/getting-started/creating-flows',
        component: ComponentCreator('/getting-started/creating-flows', '362'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/getting-started/hugging-face-spaces',
        component: ComponentCreator('/getting-started/hugging-face-spaces', 'a7a'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/getting-started/installation',
        component: ComponentCreator('/getting-started/installation', 'd04'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/guidelines/collection',
        component: ComponentCreator('/guidelines/collection', '0cc'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/guidelines/components',
        component: ComponentCreator('/guidelines/components', 'df5'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/guidelines/features',
        component: ComponentCreator('/guidelines/features', '648'),
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
