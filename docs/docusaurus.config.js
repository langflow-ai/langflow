// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");
const { remarkCodeHike } = require("@code-hike/mdx");

const isProduction = process.env.NODE_ENV === "production";

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Langflow Documentation",
  tagline:
    "Langflow is a low-code app builder for RAG and multi-agent AI applications.",
  favicon: "img/favicon.ico",
  url: "https://docs.langflow.org",
  baseUrl: process.env.BASE_URL ? process.env.BASE_URL : "/",
  onBrokenLinks: "warn",
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
    },
    ...(isProduction
      ? [
          // Ketch consent management script
          {
            tagName: "script",
            attributes: {},
            innerHTML: `!function(){window.semaphore=window.semaphore||[],window.ketch=function(){window.semaphore.push(arguments)};var e=document.createElement("script");e.type="text/javascript",e.src="https://global.ketchcdn.com/web/v3/config/datastax/langflow_org_web/boot.js",e.defer=e.async=!0,document.getElementsByTagName("head")[0].appendChild(e)}();`,
          },
          // Ketch jurisdiction dynamic link and GA4 consent tracking
          {
            tagName: "script",
            attributes: {
              defer: "true",
            },
            innerHTML: `
          ;(function () {
            const onKetchConsentGtagTrack = (consent) => {
              if (window.gtag &&
                  consent.purposes &&
                  'analytics' in consent.purposes &&
                  'targeted_advertising' in consent.purposes
              ) {
                const analyticsString = consent.purposes.analytics === true ? 'granted' : 'denied'
                const targetedAdsString = consent.purposes.targeted_advertising === true ? 'granted' : 'denied'
                const gtagObject = {
                  analytics_storage: analyticsString,
                  ad_personalization: targetedAdsString,
                  ad_storage: targetedAdsString,
                  ad_user_data: targetedAdsString,
                }
                window.gtag('consent', 'update', gtagObject)
              }
            }
            if (window.ketch) {
              window.ketch('on', 'consent', onKetchConsentGtagTrack)
            }
          })()
        `,
          },
        ]
      : []),
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
          ignorePatterns: ["/preferences"],
        },
        gtag: {
          trackingID: "G-SLQFLQ3KPT",
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
            to: "/docs/get-started-installation",
            from: [
              "/getting-started-installation",
              "/getting-started-common-installation-issues",
            ],
          },
          {
            to: "/docs/get-started-quickstart",
            from: "/getting-started-quickstart",
          },
          {
            to: "/docs/concepts-overview",
            from: [
              "/workspace-overview",
              "/365085a8-a90a-43f9-a779-f8769ec7eca1",
              "/My-Collection",
              "/workspace",
              "/settings-project-general-settings",
            ],
          },
          {
            to: "/docs/concepts-components",
            from: ["/components", "/components-overview"],
          },
          {
            to: "/docs/configuration-global-variables",
            from: "/settings-global-variables",
          },
          {
            to: "/docs/concepts-playground",
            from: [
              "/workspace-playground",
              "/workspace-logs",
              "/guides-chat-memory",
            ],
          },
          {
            to: "/docs/concepts-objects",
            from: ["/guides-data-message", "/configuration-objects"],
          },
          {
            to: "/docs/blog-writer",
            from: ["/starter-projects-blog-writer", "/tutorials-blog-writer"],
          },
          {
            to: "/docs/memory-chatbot",
            from: [
              "/starter-projects-memory-chatbot",
              "/tutorials-memory-chatbot",
            ],
          },
          {
            to: "/docs/document-qa",
            from: ["/starter-projects-document-qa", "/tutorials-document-qa"],
          },
          {
            to: "/docs/simple-agent",
            from: [
              "/math-agent",
              "/starter-projects-simple-agent",
              "/starter-projects-math-agent",
              "/tutorials-math-agent",
            ],
          },
          {
            to: "/docs/sequential-agent",
            from: [
              "/starter-projects-sequential-agent",
              "/tutorials-sequential-agent",
            ],
          },
          {
            to: "/docs/travel-planning-agent",
            from: [
              "/starter-projects-travel-planning-agent",
              "/tutorials-travel-planning-agent",
              "/starter-projects-dynamic-agent/",
            ],
          },
          {
            to: "/docs/components-vector-stores",
            from: "/components-rag",
          },
          {
            to: "/docs/configuration-authentication",
            from: [
              "/configuration-security-best-practices",
              "/Configuration/configuration-security-best-practices",
            ],
          },
          {
            to: "/docs/environment-variables",
            from: [
              "/configuration-auto-saving",
              "/Configuration/configuration-auto-saving",
              "/configuration-backend-only",
              "/Configuration/configuration-backend-only",
            ],
          },
          {
            to: "/docs/concepts-publish",
            from: ["/concepts-api", "/workspace-api"],
          },
          {
            to: "/docs/components-custom-components",
            from: "/components/custom",
          },
          {
            to: "/docs/components-bundle-components",
            from: "/components-loaders",
          },
          {
            to: "/docs/mcp-server",
            from: "/integrations-mcp",
          },
          {
            to: "/docs/integrations-nvidia-g-assist",
            from: "/integrations-nvidia-system-assist",
          },
          {
            to: "/docs/deployment-kubernetes-dev",
            from: [
              "/deployment-kubernetes",
            ],
          },
          {
            to: "/docs/basic-prompting",
            from: "/starter-projects-basic-prompting",
          },
          {
            to: "/docs/vector-store-rag",
            from: "/starter-projects-vector-store-rag",
          },
          {
            to: "/docs/contributing-github-issues",
            from: "/contributing-github-discussions",
          },
          {
            to: "/docs/agents",
            from: "/agents-tool-calling-agent-component",
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
          src: "img/lf-docs-light.svg",
          srcDark: "img/lf-docs-dark.svg",
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
      footer: {
        links: [
          {
            title: null,
            items: [
              {
                html: `<div class="footer-links">
                  <span>© ${new Date().getFullYear()} Langflow</span>
                  <span id="preferenceCenterContainer"> ·&nbsp; <a href="https://langflow.org/preferences">Manage Privacy Choices</a></span>
                  </div>`,
              },
            ],
          },
        ],
      },
      algolia: {
        appId: "UZK6BDPCVY",
        // public key, safe to commit
        apiKey: "adbd7686dceb1cd510d5ce20d04bf74c",
        indexName: "langflow",
        contextualSearch: true,
        searchParameters: {},
        searchPagePath: "search",
      },
    }),
};

module.exports = config;
