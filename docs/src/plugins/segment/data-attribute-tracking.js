import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

let isDataAttributeTrackingInitialized = false;

/**
 * Automatic click tracking using data attributes for Docusaurus
 *
 * Usage: Add data-event and other data-* attributes to any clickable element.
 * The tracker will automatically send events to Segment when clicked.
 *
 * Example in navbar config:
 * {
 *   href: "https://github.com/langflow-ai/langflow",
 *   'data-event': 'GitHub Link Clicked',
 *   'data-source': 'navbar',
 *   'data-category': 'social'
 * }
 *
 * This will automatically call:
 * window.analytics.track("GitHub Link Clicked", {
 *   source: "navbar",
 *   category: "social",
 *   url: "https://github.com/langflow-ai/langflow",
 *   page: "/current-page"
 * })
 */
function initializeDataAttributeTracking() {
  // Only run on client side and prevent duplicate initialization
  if (!ExecutionEnvironment.canUseDOM || isDataAttributeTrackingInitialized) return;

  const handleClick = (event) => {
    const target = event.target;
    const trackingElement = target.closest('[data-event]');

    if (!trackingElement) return;

    const eventName = trackingElement.dataset.event;
    if (!eventName) return;

    // Extract all data-* attributes (except data-event itself)
    const properties = {};

    Object.keys(trackingElement.dataset).forEach(key => {
      if (key !== 'event') {
        // Convert camelCase to snake_case for consistency
        const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase();
        properties[snakeKey] = trackingElement.dataset[key];
      }
    });

    // Track the event
    if (window.analytics && typeof window.analytics.track === 'function') {
      window.analytics.track(eventName, properties);
    } else {
      console.warn('Analytics not available for tracking:', eventName, properties);
    }
  };

  // Remove existing listener if it exists
  document.removeEventListener('click', handleClick);

  // Add the new listener
  document.addEventListener('click', handleClick);

  // Mark as initialized
  isDataAttributeTrackingInitialized = true;
}

// Initialize on DOM ready
if (ExecutionEnvironment.canUseDOM) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDataAttributeTracking);
  } else {
    initializeDataAttributeTracking();
  }

  // Re-initialize on route changes for SPA navigation
  window.addEventListener('popstate', () => {
    setTimeout(initializeDataAttributeTracking, 100);
  });
}
