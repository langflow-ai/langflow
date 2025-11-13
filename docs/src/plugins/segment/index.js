// Custom Docusaurus plugin to inject Segment analytics
function pluginSegment(context, options = {}) {
  const isProd = process.env.NODE_ENV === "production" || options.allowedInDev;
  const segmentPublicWriteKey = options.segmentPublicWriteKey;

  if (!segmentPublicWriteKey) {
    console.warn('Segment plugin: No write key provided. Analytics will not be initialized.');
    return { name: 'docusaurus-plugin-segment' };
  }

  return {
    name: 'docusaurus-plugin-segment',

    getClientModules() {
      return isProd ? [require.resolve('./analytics-page'), require.resolve('./data-attribute-tracking')] : [];
    },

    injectHtmlTags() {
      if (!isProd) {
        return {};
      }

      return {
        headTags: [
          // IBM Analytics and TrustArc Configuration
          {
            tagName: 'script',
            attributes: {},
            innerHTML: `
              window._ibmAnalytics = {
                "settings": {
                  "name": "DataStax",
                  "tealiumProfileName": "ibm-subsidiary",
                },
                "trustarc": {
                  "privacyPolicyLink": "https://ibm.com/privacy"
                },
                "digitalData.page.services.google.enabled": true
              };
              window.digitalData = {
                "page": {
                  "pageInfo": {
                    "ibm": {
                      "siteId": "IBM_" + _ibmAnalytics.settings.name,
                    },
                    segment: {
                      enabled: true,
                      env: 'prod',
                      key: '${segmentPublicWriteKey}',
                      coremetrics: false,
                      carbonComponentEvents: false
                    }
                  },
                  "category": {
                    "primaryCategory": "PC230"
                  }
                },
                "commonProperties": {
                  "productTitle": "IBM Elite Support for Langflow",
                  "productCode": "5900BUB",
                  "productCodeType": "WWPC",
                  "UT30": "30AS5",
                  "instanceId": "docs-site",
                  "subscriptionId": "public-access",
                  "productPlanName": "Public",
                  "productPlanType": "freemium",
                  "userId": "IBMid-ANONYMOUS"
                }
              };
            `,
          },
          // IBM Common Stats Script - handles Segment initialization
          {
            tagName: 'script',
            attributes: {
              src: '//1.www.s81c.com/common/stats/ibm-common.js',
              async: 'true',
            },
          },
        ],
      };
    },
  };
}

module.exports = pluginSegment;
