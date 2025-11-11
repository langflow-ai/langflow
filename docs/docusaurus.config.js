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
    },
    ...(isProduction
      ? [
          // Google Consent Mode - Set defaults before Google tags load
          {
            tagName: "script",
            attributes: {},
            innerHTML: `
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}

              // Set default consent to denied
              gtag('consent', 'default', {
                'ad_storage': 'denied',
                'ad_user_data': 'denied',
                'ad_personalization': 'denied',
                'analytics_storage': 'denied'
              });
            `,
          },
          // TrustArc Consent Update Listener
          {
            tagName: "script",
            attributes: {},
            innerHTML: `
              (function() {
                function updateGoogleConsent() {
                  if (typeof window.truste !== 'undefined' && window.truste.cma) {
                    var consent = window.truste.cma.callApi('getConsent', window.location.href) || {};

                    // Map TrustArc categories to Google consent types
                    // Category 0 = Required, 1 = Functional, 2 = Advertising, 3 = Analytics
                    var hasAdvertising = consent[2] === 1;
                    var hasAnalytics = consent[3] === 1;

                    gtag('consent', 'update', {
                      'ad_storage': hasAdvertising ? 'granted' : 'denied',
                      'ad_user_data': hasAdvertising ? 'granted' : 'denied',
                      'ad_personalization': hasAdvertising ? 'granted' : 'denied',
                      'analytics_storage': hasAnalytics ? 'granted' : 'denied'
                    });
                  }
                }

                // Listen for consent changes
                if (window.addEventListener) {
                  window.addEventListener('cm_data_subject_consent_changed', updateGoogleConsent);
                  window.addEventListener('cm_consent_preferences_set', updateGoogleConsent);
                }

                // Initial check after TrustArc loads
                if (document.readyState === 'complete') {
                  updateGoogleConsent();
                } else {
                  window.addEventListener('load', updateGoogleConsent);
                }
              })();
            `,
          },
        ]
      : []),
  ],

  presets: [
    [
      "@docusaurus/preset-classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
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
          ignorePatterns: [],
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
    [
      "redocusaurus",
      {
        openapi: {
          path: "openapi",
          routeBasePath: "/api",
        },
        specs: [
          {
            id: "api",
            spec: "openapi/openapi.json",
            route: "/api",
          },
        ],
        theme: {
          primaryColor: "#7528FC",
        },
      },
    ],
  ],
  plugins: [
    ["docusaurus-node-polyfills", { excludeAliases: ["console"] }],
    "docusaurus-plugin-image-zoom",
    ["./src/plugins/segment", { segmentPublicWriteKey: process.env.SEGMENT_PUBLIC_WRITE_KEY, allowedInDev: true }],
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
              "/guides-new-to-llms",
              "/about-langflow",
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
            to: "/concepts-overview",
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
            from: ["/components", "/components-overview"],
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
            to: "/data-types",
            from: ["/guides-data-message", "/configuration-objects"],
          },
          {
            to: "/concepts-flows",
            from: [
              "/travel-planning-agent",
              "/starter-projects-travel-planning-agent",
              "/tutorials-travel-planning-agent",
              "/starter-projects-dynamic-agent/",
              "/simple-agent",
              "/math-agent",
              "/starter-projects-simple-agent",
              "/starter-projects-math-agent",
              "/tutorials-math-agent",
              "/sequential-agent",
              "/starter-projects-sequential-agent",
              "/tutorials-sequential-agent",
              "/memory-chatbot",
              "/starter-projects-memory-chatbot",
              "/tutorials-memory-chatbot",
              "/financial-report-parser",
              "/document-qa",
              "/starter-projects-document-qa",
              "/tutorials-document-qa",
              "/blog-writer",
              "/starter-projects-blog-writer",
              "/tutorials-blog-writer",
              "/basic-prompting",
              "/starter-projects-basic-prompting",
              "/vector-store-rag",
              "/starter-projects-vector-store-rag",
            ],
          },
          {
            to: "/components-bundle-components",
            from: [
              "/components-rag",
              "/components-vector-stores",
              "/components-loaders",
            ],
          },
          {
            to: "/api-keys-and-authentication",
            from: [
              "/configuration-api-keys",
              "/configuration-authentication",
              "/configuration-security-best-practices",
              "/Configuration/configuration-security-best-practices",
            ],
          },
          {
            to: "/environment-variables",
            from: [
              "/configuration-auto-saving",
              "/Configuration/configuration-auto-saving",
              "/configuration-backend-only",
              "/Configuration/configuration-backend-only",
            ],
          },
          {
            to: "/concepts-publish",
            from: [
              "/concepts-api",
              "/workspace-api",
            ],
          },
          {
            to: "/components-custom-components",
            from: "/components/custom",
          },
          {
            to: "/mcp-server",
            from: "/integrations-mcp",
          },
          {
            to: "/deployment-kubernetes-dev",
            from: "/deployment-kubernetes",
          },
          {
            to: "/contributing-github-issues",
            from: "/contributing-github-discussions",
          },
          {
            to: "/agents",
            from: "/agents-tool-calling-agent-component",
          },
          {
            to: "/concepts-publish",
            from: "/embedded-chat-widget",
          },
          {
            to: "/bundles-google",
            from: [
              "/integrations-setup-google-oauth-langflow",
              "/integrations-google-big-query",
            ],
          },
          {
            to: "/bundles-vertexai",
            from: "/integrations-setup-google-cloud-vertex-ai-langflow",
          },
          {
            to: "/develop-application",
            from: "/develop-overview",
          },
          {
            to: "/data-types",
            from: "/concepts-objects",
          },
          {
            to: "/components-helpers",
            from: "/components-memories",
          },
          {
            to: "/bundles-apify",
            from: "/integrations-apify",
          },
          {
            to: "/bundles-assemblyai",
            from: "/integrations-assemblyai",
          },
          {
            to: "/bundles-cleanlab",
            from: "/integrations-cleanlab",
          },
          {
            to: "/bundles-composio",
            from: "/integrations-composio",
          },
          {
            to: "/bundles-docling",
            from: "/integrations-docling",
          },
          {
            to: "/bundles-notion",
            from: [
              "/integrations/notion/setup",
              "/integrations/notion/notion-agent-meeting-notes",
              "/integrations/notion/notion-agent-conversational",
            ],
          },
          {
            to: "/bundles-nvidia",
            from: [
              "/integrations-nvidia-ingest-wsl2",
              "/integrations-nvidia-ingest",
              "/integrations-nvidia-g-assist",
              "/integrations-nvidia-system-assist",
            ]
          }
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
            'data-event': 'UI Interaction',
            'data-action': 'clicked',
            'data-channel': 'docs',
            'data-element-id': 'social-github',
            'data-namespace': 'header',
            'data-platform-title': 'Langflow'
          },
          {
            position: "right",
            href: "https://twitter.com/langflow_ai",
            className: "header-twitter-link",
            target: "_blank",
            rel: null,
            'data-event': 'UI Interaction',
            'data-action': 'clicked',
            'data-channel': 'docs',
            'data-element-id': 'social-twitter',
            'data-namespace': 'header',
            'data-platform-title': 'Langflow'
          },
          {
            position: "right",
            href: "https://discord.gg/EqksyE2EX9",
            className: "header-discord-link",
            target: "_blank",
            rel: null,
            'data-event': 'UI Interaction',
            'data-action': 'clicked',
            'data-channel': 'docs',
            'data-element-id': 'social-discord',
            'data-namespace': 'header',
            'data-platform-title': 'Langflow'
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
          autoCollapseCategories: true,
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
                  <span id="preferenceCenterContainer"> ·&nbsp; <a href="#" onclick="if(typeof window !== 'undefined' && window.truste && window.truste.eu && window.truste.eu.clickListener) { window.truste.eu.clickListener(); } return false;" style="cursor: pointer;">Manage Privacy Choices</a></span>
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
