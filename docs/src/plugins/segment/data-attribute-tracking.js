import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';
import { identifyUser, trackEvent } from './analytics-helpers';

let isDataAttributeTrackingInitialized = false;

/**
 * Automatic click tracking using data attributes for Docusaurus
 *
 * Usage: Add data-event and other data-* attributes to any clickable element.
 * The tracker will automatically send events to Segment when clicked.
 *
 * Example - UI Interaction:
 * {
 *   href: "https://github.com/langflow-ai/langflow",
 *   'data-event': 'UI Interaction',
 *   'data-action': 'clicked',
 *   'data-channel': 'docs',
 *   'data-element-id': 'social-github',
 *   'data-namespace': 'header',
 *   'data-platform-title': 'Langflow'
 * }
 *
 * Example - CTA Clicked:
 * {
 *   'data-event': 'CTA Clicked',
 *   'data-cta': 'Get Started',
 *   'data-channel': 'docs',
 *   'data-text': 'Get Started for Free'
 * }
 *
 * Note:
 * - data-event is required (becomes the event name)
 * - All other data-* attributes become event properties
 * - Follows IBM Segment Common Schema standards
 * - No onClick handler needed for tracking
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
        // Map to IBM Segment property names (preserve exact casing per schema)
        let propertyKey = key;

        // Handle special IBM property mappings
        if (key === 'cta') propertyKey = 'CTA';
        else if (key === 'elementId') propertyKey = 'elementId';
        else if (key === 'topLevel') propertyKey = 'topLevel';
        else if (key === 'subLevel') propertyKey = 'subLevel';
        else if (key === 'platformTitle') propertyKey = 'platformTitle';

        properties[propertyKey] = trackingElement.dataset[key];
      }
    });

    // Identify user before tracking
    identifyUser();

    // Track the event with common properties
    trackEvent(eventName, properties);
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
