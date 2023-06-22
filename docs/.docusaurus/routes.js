import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/__docusaurus/debug',
    component: ComponentCreator('/__docusaurus/debug', 'd49'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/config',
    component: ComponentCreator('/__docusaurus/debug/config', 'c5a'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/content',
    component: ComponentCreator('/__docusaurus/debug/content', 'c19'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/globalData',
    component: ComponentCreator('/__docusaurus/debug/globalData', '338'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/metadata',
    component: ComponentCreator('/__docusaurus/debug/metadata', '39f'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/registry',
    component: ComponentCreator('/__docusaurus/debug/registry', 'e70'),
    exact: true
  },
  {
    path: '/__docusaurus/debug/routes',
    component: ComponentCreator('/__docusaurus/debug/routes', 'b1f'),
    exact: true
  },
  {
    path: '/markdown-page',
    component: ComponentCreator('/markdown-page', 'b57'),
    exact: true
  },
  {
    path: '/',
    component: ComponentCreator('/', '5b5'),
    routes: [
      {
        path: '/',
        component: ComponentCreator('/', '08f'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/buffer-memory',
        component: ComponentCreator('/buffer-memory', '859'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/collection',
        component: ComponentCreator('/collection', '373'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/community',
        component: ComponentCreator('/community', '80d'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/components',
        component: ComponentCreator('/components', '997'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/conversation-chain',
        component: ComponentCreator('/conversation-chain', 'cb6'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/creating-flows',
        component: ComponentCreator('/creating-flows', '058'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/csv-loader',
        component: ComponentCreator('/csv-loader', 'bb7'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/features',
        component: ComponentCreator('/features', 'ef0'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/gcp-deployment',
        component: ComponentCreator('/gcp-deployment', '1f3'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/github-issues',
        component: ComponentCreator('/github-issues', '385'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/how-contribute',
        component: ComponentCreator('/how-contribute', '5ea'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/how-upload-examples',
        component: ComponentCreator('/how-upload-examples', '143'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/hugging-face-spaces',
        component: ComponentCreator('/hugging-face-spaces', 'dd3'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/installation',
        component: ComponentCreator('/installation', 'd10'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/jina-deployment',
        component: ComponentCreator('/jina-deployment', '370'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/midjourney-prompt-chain',
        component: ComponentCreator('/midjourney-prompt-chain', 'ef0'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/multiple-vectorstores',
        component: ComponentCreator('/multiple-vectorstores', '293'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/python-function',
        component: ComponentCreator('/python-function', 'c91'),
        exact: true,
        sidebar: "docs"
      },
      {
        path: '/serp-api-tool',
        component: ComponentCreator('/serp-api-tool', '558'),
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
