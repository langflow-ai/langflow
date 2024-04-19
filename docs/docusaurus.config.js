const lightCodeTheme = require("prism-react-renderer/themes/github");

const { remarkCodeHike } = require("@code-hike/mdx");
// With JSDoc @type annotations, IDEs can provide config autocompletion
/** @type {import('@docusaurus/types').DocusaurusConfig} */
module.exports = {
  title: "Langflow Documentation",
  tagline: "Langflow is a GUI for LangChain, designed with react-flow",
  favicon: "img/favicon.ico",
  url: "https://langflow-ai.github.io",
  baseUrl: "/",
  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "warn",
  organizationName: "langflow-ai",
  projectName: "langflow",
  trailingSlash: false,
  staticDirectories: ["static"],
  customFields: {
    mendableAnonKey: process.env.MENDABLE_ANON_KEY,
  },
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },
  presets: [
    [
      "@docusaurus/preset-classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
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
          routeBasePath: "/",
          sidebarPath: require.resolve("./sidebars.js"),
          path: "docs",
          // sidebarPath: 'sidebars.js',
        },
        gtag: {
          trackingID: "G-XHC7G628ZP",
          anonymizeIP: true,
        },
        theme: {
          customCss: [
            require.resolve("@code-hike/mdx/styles.css"),
            require.resolve("./src/css/custom.css"),
          ],
        },
      }),
    ],
  ],
  plugins: [
    ["docusaurus-node-polyfills", { excludeAliases: ["console"] }],
    "docusaurus-plugin-image-zoom",
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
  themes: ["mdx-v2"],
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        hideOnScroll: true,
        title: "Langflow",
        logo: {
          alt: "Langflow",
          src: "img/chain.png",
        },
        items: [
          // right
          {
            position: "right",
            href: "https://github.com/langflow-ai/langflow",
            position: "right",
            className: "header-github-link",
            target: "_blank",
            rel: null,
          },
          {
            position: "right",
            href: "https://twitter.com/langflow_ai",
            position: "right",
            className: "header-twitter-link",
            target: "_blank",
            rel: null,
          },
          {
            position: "right",
            href: "https://discord.gg/EqksyE2EX9",
            position: "right",
            className: "header-discord-link",
            target: "_blank",
            rel: null,
          },
        ],
      },
      tableOfContents: {
        minHeadingLevel: 2,
        maxHeadingLevel: 5,
      },
      colorMode: {
        defaultMode: "light",
        /* Allow users to chose light or dark mode. */
        disableSwitch: false,
        /* Respect user preferences, such as low light mode in the evening */
        respectPrefersColorScheme: true,
      },
      announcementBar: {
        content:
          '⭐️ If you like ⛓️Langflow, star it on <a target="_blank" rel="noopener noreferrer" href="https://github.com/langflow-ai/langflow">GitHub</a>! ⭐️',
        backgroundColor: "#E8EBF1", //Mustard Yellow #D19900 #D4B20B - Salmon #E9967A
        textColor: "#1C1E21",
        isCloseable: false,
      },
      footer: {
        links: [],
        copyright: `Copyright © ${new Date().getFullYear()} Langflow.`,
      },
      zoom: {
        selector: ".markdown :not(a) > img:not(.no-zoom)",
        background: {
          light: "rgba(240, 240, 240, 0.9)",
        },
        config: {},
      },
      // prism: {
      //   theme: require("prism-react-renderer/themes/dracula"),
      // },
      docs: {
        sidebar: {
          hideable: true,
        },
      },
    }),
};
