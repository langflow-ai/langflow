/**
 * Get common properties that should be included in all events
 */
export function getCommonProperties() {
  if (typeof window === 'undefined' || !window.digitalData?.commonProperties) {
    return {};
  }

  return {
    productTitle: window.digitalData.commonProperties.productTitle,
    productCode: window.digitalData.commonProperties.productCode,
    productCodeType: window.digitalData.commonProperties.productCodeType,
    UT30: window.digitalData.commonProperties.UT30,
    instanceId: window.digitalData.commonProperties.instanceId,
    subscriptionId: window.digitalData.commonProperties.subscriptionId,
    productPlanName: window.digitalData.commonProperties.productPlanName,
    productPlanType: window.digitalData.commonProperties.productPlanType,
  };
}

/**
 * Get user ID for identify calls
 */
export function getUserId() {
  if (typeof window === 'undefined' || !window.digitalData?.commonProperties) {
    return 'IBMid-ANONYMOUS';
  }

  return window.digitalData.commonProperties.userId || 'IBMid-ANONYMOUS';
}

/**
 * Call identify with required properties
 * Should be called before any track events
 */
export function identifyUser() {
  if (typeof window === 'undefined' || !window.analytics?.identify) {
    return;
  }

  const userId = getUserId();
  const traits = getCommonProperties();

  window.analytics.identify(userId, traits);
}

/**
 * Enhanced track function that includes common properties
 */
export function trackEvent(eventName, properties = {}) {
  if (typeof window === 'undefined' || !window.analytics?.track) {
    return;
  }

  const commonProps = getCommonProperties();
  const mergedProperties = { ...commonProps, ...properties };

  window.analytics.track(eventName, mergedProperties);
}

/**
 * Enhanced page function that includes common properties
 */
export function trackPage(name, properties = {}) {
  if (typeof window === 'undefined' || !window.analytics?.page) {
    return;
  }

  const commonProps = getCommonProperties();
  const mergedProperties = { ...commonProps, ...properties };

  window.analytics.page(name, mergedProperties);
}
