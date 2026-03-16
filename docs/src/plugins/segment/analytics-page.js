import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';
import { identifyUser, trackPage } from './analytics-helpers';

/**
 * Get friendly page name from pathname
 */
function getFriendlyPageName(pathname) {
  // Remove leading/trailing slashes
  const cleanPath = pathname.replace(/^\/+|\/+$/g, '');

  // Handle root/home page
  if (!cleanPath) {
    return 'Home';
  }

  // Split by slash and capitalize each segment
  const segments = cleanPath.split('/');
  const formattedSegments = segments.map(segment => {
    // Replace hyphens with spaces and capitalize
    return segment
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  });

  return formattedSegments.join(' > ');
}

// Client module for tracking page views on route changes
export function onRouteDidUpdate({location, previousLocation}) {
  // Only track page views in the browser and when the path actually changes
  if (
    ExecutionEnvironment.canUseDOM &&
    previousLocation &&
    location.pathname !== previousLocation.pathname &&
    window.analytics &&
    window.analytics.page
  ) {
    // Identify user before tracking page
    identifyUser();

    // Track page with friendly name
    const pageName = getFriendlyPageName(location.pathname);
    trackPage(pageName, {
      path: location.pathname,
      url: location.href,
      search: location.search,
      title: document.title,
    });
  }
}

// Initial page view on load
if (ExecutionEnvironment.canUseDOM) {
  window.addEventListener('load', () => {
    if (window.analytics && window.analytics.page) {
      // Identify user on initial page load
      identifyUser();

      // Track initial page view
      const pageName = getFriendlyPageName(window.location.pathname);
      trackPage(pageName, {
        path: window.location.pathname,
        url: window.location.href,
        search: window.location.search,
        title: document.title,
      });
    }
  });
}
