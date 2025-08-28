// Default configuration shared between client and server
const DEFAULT_SELECTORS = [
  {
    selector: 'h1, h2, h3, h4, h5, h6',
    eventName: 'Scroll - Heading Viewed',
    properties: {
      element_type: 'heading'
    }
  }
];

// Custom Docusaurus plugin for scroll tracking with Segment analytics
function pluginScrollTracking(context, options = {}) {
  const isProd = process.env.NODE_ENV === "production" || options.allowedInDev;
  const segmentPublicWriteKey = options.segmentPublicWriteKey;

  if (!segmentPublicWriteKey) {
    console.warn('Scroll tracking plugin: No Segment write key provided. Analytics will not be initialized.');
    return { name: 'docusaurus-plugin-scroll-tracking' };
  }

  return {
    name: 'docusaurus-plugin-scroll-tracking',

    getClientModules() {
      return isProd ? [require.resolve('./scroll-tracking')] : [];
    },

    injectHtmlTags() {
      if (!isProd) {
        return {};
      }

      // Inject configuration into global scope for client-side access
      const config = {
        selectors: options.selectors || DEFAULT_SELECTORS
      };
      
      const configScript = `
        window.__SCROLL_TRACKING_CONFIG__ = ${JSON.stringify(config)};
      `;

      return {
        headTags: [
          {
            tagName: 'script',
            innerHTML: configScript,
          },
        ],
      };
    },
  };
}

module.exports = pluginScrollTracking;