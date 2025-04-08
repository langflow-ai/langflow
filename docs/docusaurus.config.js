// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");
const { remarkCodeHike } = require("@code-hike/mdx");

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Langflow Documentation",
  tagline:
    "Langflow is a low-code app builder for RAG and multi-agent AI applications.",
  favicon: "img/favicon.ico",
  url: "https://docs.langflow.org",
  baseUrl: process.env.BASE_URL ? process.env.BASE_URL : "/",
  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "warn",
  onBrokenAnchors: "warn",
  organizationName: "langflow-ai",
  projectName: "langflow",
  trailingSlash: false,
  staticDirectories: ["static"],
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },
  headTags: [
    {
      tagName: "link",
      attributes: {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Sora:wght@550;600&display=swap",
      },
    }
  ],

  presets: [
    [
      "docusaurus-preset-openapi",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        api: {
          path: "openapi.json", // Path to your OpenAPI file
          routeBasePath: "/api", // The base URL for your API docs
        },
        docs: {
          routeBasePath: "/", // Serve the docs at the site's root
          sidebarPath: require.resolve("./sidebars.js"), // Use sidebars.js file
          sidebarCollapsed: true,
          beforeDefaultRemarkPlugins: [
            [
              remarkCodeHike,
              {
                theme: "github-dark",
                showCopyButton: true,
                lineNumbers: true,
              },
            ],
          ],
        },
        sitemap: {
          // https://docusaurus.io/docs/api/plugins/@docusaurus/plugin-sitemap
          // https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
          lastmod: "datetime",
          changefreq: null,
          priority: null,
        },
        gtag: {
          trackingID: "G-L8Y98PSEMQ",
        },
        blog: false,
        theme: {
          customCss: [
            require.resolve("@code-hike/mdx/styles.css"),
            require.resolve("./css/custom.css"),
            require.resolve("./css/docu-notion-styles.css"),
            require.resolve(
              "./css/gifplayer.css"
              //"./node_modules/react-gif-player/dist/gifplayer.css" // this gave a big red compile warning which is seaming unrelated "  Replace Autoprefixer browsers option to Browserslist config..."
            ),
          ],
        },
      }),
    ],
  ],
  plugins: [
    ["docusaurus-node-polyfills", { excludeAliases: ["console"] }],
    "docusaurus-plugin-image-zoom",
    [
      "@docusaurus/plugin-client-redirects",
      {
        redirects: [
          {
            to: "/",
            from: [
              "/whats-new-a-new-chapter-langflow",
              "/👋 Welcome-to-Langflow",
              "/getting-started-welcome-to-langflow",
              "/guides-new-to-llms"
            ],
          },
          {
            to: "/get-started-installation",
            from: [
              "/getting-started-installation",
              "/getting-started-common-installation-issues",
            ],
          },
          {
            to: "/get-started-quickstart",
            from: "/getting-started-quickstart",
          },
          {
            to: "concepts-overview",
            from: [
              "/workspace-overview",
              "/365085a8-a90a-43f9-a779-f8769ec7eca1",
              "/My-Collection",
              "/workspace",
              "/settings-project-general-settings",
            ],
          },
          {
            to: "/concepts-components",
            from: [
              "/components",
              "/components-overview"
            ],
          },
          {
            to: "/configuration-global-variables",
            from: "/settings-global-variables",
          },
          {
            to: "/concepts-playground",
            from: [
              "/workspace-playground",
              "/workspace-logs",
              "/guides-chat-memory",
            ],
          },
          {
            to: "/concepts-objects",
            from: [
              "/guides-data-message",
              "/configuration-objects",
            ]
          },
          {
            to: "/blog-writer",
            from: [
              "/starter-projects-blog-writer",
              "/tutorials-blog-writer"
            ],
          },
          {
            to: "/memory-chatbot",
            from: [
              "/starter-projects-memory-chatbot",
              "/tutorials-memory-chatbot"
            ],
          },
          {
            to: "/document-qa",
            from: [
              "/starter-projects-document-qa",
              "/tutorials-document-qa"
            ],
          },
          {
            to: "/starter-projects-simple-agent",
            from: [
              "/math-agent",
              "/starter-projects-math-agent",
              "/tutorials-math-agent"
            ],
          },
          {
            to: "/sequential-agent",
            from: [
              "/starter-projects-sequential-agent",
              "/tutorials-sequential-agent"
            ],
          },
          {
            to: "/travel-planning-agent",
            from: [
              "/starter-projects-travel-planning-agent",
              "/tutorials-travel-planning-agent",
              "/starter-projects-dynamic-agent/",
            ],
          },
          {
            to: "/components-vector-stores",
            from: "/components-rag",
          },
          {
            to: "/configuration-authentication",
            from: [
              "/configuration-security-best-practices",
              "/Configuration/configuration-security-best-practices"
            ],
          },
          {
            to: "/environment-variables",
            from: [
              "/configuration-auto-saving",
              "/Configuration/configuration-auto-saving",
              "/configuration-backend-only",
              "/Configuration/configuration-backend-only"
            ],
          },
          {
            to: "/concepts-publish",
            from: [
              "/concepts-api",
              "/workspace-api",
            ]
          },
          {
            to: "/components-custom-components",
            from: "/components/custom",
          },
          // add more redirects like this
          // {
          //   to: '/docs/anotherpage',
          //   from: ['/docs/legacypage1', '/docs/legacypage2'],
          // },
        ],
      },
    ],
    // ....
    async function myPlugin(context, options) {
      return {
        name: "docusaurus-tailwindcss",
        configurePostCss(postcssOptions) {
          // Appends TailwindCSS and AutoPrefixer.
          postcssOptions.plugins.push(require("tailwindcss"));
          postcssOptions.plugins.push(require("autoprefixer"));
          return postcssOptions;
        },
      };
    },
  ],
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        hideOnScroll: true,
        logo: {
          alt: "Langflow",
          src: "img/langflow-logo-black.svg",
          srcDark: "img/langflow-logo-white.svg",
        },
        items: [
          // right
          {
            position: "right",
            href: "https://github.com/langflow-ai/langflow",
            className: "header-github-link",
            target: "_blank",
            rel: null,
          },
          {
            position: "right",
            href: "https://twitter.com/langflow_ai",
            className: "header-twitter-link",
            target: "_blank",
            rel: null,
          },
          {
            position: "right",
            href: "https://discord.gg/EqksyE2EX9",
            className: "header-discord-link",
            target: "_blank",
            rel: null,
          },
        ],
      },
      colorMode: {
        defaultMode: "light",
        /* Allow users to chose light or dark mode. */
        disableSwitch: false,
        /* Respect user preferences, such as low light mode in the evening */
        respectPrefersColorScheme: true,
      },
      prism: {
        theme: lightCodeTheme,
        darkTheme: darkCodeTheme,
      },
      zoom: {
        selector: ".markdown :not(a) > img:not(.no-zoom)",
        background: {
          light: "rgba(240, 240, 240, 0.9)",
        },
        config: {},
      },
      docs: {
        sidebar: {
          hideable: false,
        },
      },
      algolia: {
        appId: 'UZK6BDPCVY',
        // public key, safe to commit
        apiKey: 'adbd7686dceb1cd510d5ce20d04bf74c',
        indexName: 'langflow',
        contextualSearch: true,
        searchParameters: {},
        searchPagePath: 'search',
      },
    }),
};

module.exports = config;
