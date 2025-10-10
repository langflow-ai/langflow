import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

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
    window.analytics.page();
  }
}
