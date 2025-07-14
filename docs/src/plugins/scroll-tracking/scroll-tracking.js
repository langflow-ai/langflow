import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';

let isScrollTrackingInitialized = false;

// Helper functions for extracting dynamic properties
const propertyHelpers = {
  // Extract data-ch-lang attribute from code elements
  codeLanguage: (element) => {
    const codeElement = element.querySelector('[data-ch-lang]') || 
                       element.closest('[data-ch-lang]');
    return codeElement?.getAttribute('data-ch-lang') || null;
  }
};

// Default configuration (fallback if no config is injected)
const defaultConfig = {
  selectors: [
    {
      selector: 'h1, h2, h3, h4, h5, h6',
      eventName: 'Scroll - Heading Viewed',
      properties: {
        element_type: 'heading'
      }
    }
  ]
};

/**
 * Get scroll depth percentage
 */
function getScrollDepthPercentage() {
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
  const documentHeight = Math.max(
    document.body.scrollHeight,
    document.body.offsetHeight,
    document.documentElement.clientHeight,
    document.documentElement.scrollHeight,
    document.documentElement.offsetHeight
  );
  const windowHeight = window.innerHeight;
  const scrollableHeight = documentHeight - windowHeight;
  
  if (scrollableHeight <= 0) return 100;
  
  return Math.min(100, Math.round((scrollTop / scrollableHeight) * 100));
}

/**
 * Get element properties for tracking
 */
function getElementProperties(element, baseProperties = {}) {
  const properties = {};
  
  // Process base properties, handling helper function references
  Object.keys(baseProperties).forEach(key => {
    const value = baseProperties[key];
    
    if (typeof value === 'function') {
      // Direct function (for programmatic config)
      try {
        const result = value(element);
        if (result !== null && result !== undefined) {
          properties[key] = result;
        }
      } catch (error) {
        console.warn(`Scroll tracking: Error executing function for property "${key}":`, error);
      }
    } else if (typeof value === 'string' && value.startsWith('helper:')) {
      // Helper function reference (for config-based setup)
      const helperName = value.replace('helper:', '');
      if (propertyHelpers[helperName]) {
        try {
          const result = propertyHelpers[helperName](element);
          if (result !== null && result !== undefined) {
            properties[key] = result;
          }
        } catch (error) {
          console.warn(`Scroll tracking: Error executing helper "${helperName}" for property "${key}":`, error);
        }
      } else {
        console.warn(`Scroll tracking: Unknown helper function "${helperName}"`);
      }
    } else {
      properties[key] = value;
    }
  });
  
  // Add common properties
  properties.page_path = window.location.pathname;
  properties.page_url = window.location.href;
  properties.scroll_depth = getScrollDepthPercentage();
  
  // Add element-specific properties
  if (element.tagName) {
    properties.tag_name = element.tagName.toLowerCase();
  }
  
  if (element.id) {
    properties.element_id = element.id;
  }
  
  if (element.className) {
    properties.element_class = element.className;
  }
  
  // For headings, add text content and level
  if (element.tagName && element.tagName.match(/^H[1-6]$/)) {
    properties.heading_level = element.tagName.toLowerCase();
    properties.heading_text = element.textContent?.trim().substring(0, 200); // Limit text length to 200 chars
    properties.text = element.textContent?.trim().substring(0, 200); // Add 'text' property as requested
  }
  
  return properties;
}

/**
 * Set up intersection observer for element tracking
 */
function setupElementTracking(config) {
  if (!window.IntersectionObserver) {
    console.warn('IntersectionObserver not supported, element tracking disabled');
    return;
  }
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      // Fire event every time element comes into view (not just first time)
      if (entry.isIntersecting) {
        // Find matching selector config
        const selectorConfig = config.selectors.find(sc => 
          entry.target.matches(sc.selector)
        );
        
        if (selectorConfig) {
          const properties = getElementProperties(entry.target, selectorConfig.properties || {});
          
          if (window.analytics && typeof window.analytics.track === 'function') {
            window.analytics.track(selectorConfig.eventName, properties);
          }
        }
      }
    });
  }, {
    threshold: 0.1, // Element needs to be 10% visible
    rootMargin: '0px'
  });
  
  // Function to observe elements for a given selector
  const observeElementsForSelector = (selectorConfig) => {
    const elements = document.querySelectorAll(selectorConfig.selector);
    elements.forEach(element => {
      if (!element._scrollTrackingObserved) {
        observer.observe(element);
        element._scrollTrackingObserved = true;
      }
    });
  };
  
  // Observe all existing elements matching the selectors
  config.selectors.forEach(observeElementsForSelector);
  
  // Also scan after a delay for dynamically rendered content
  setTimeout(() => {
    config.selectors.forEach(observeElementsForSelector);
  }, 1000);
  
  // Set up mutation observer for dynamically added elements
  if (window.MutationObserver) {
    const mutationObserver = new MutationObserver((mutations) => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            // Check if the added node or any of its children match our selectors
            config.selectors.forEach(selectorConfig => {
              // Check the node itself
              if (node.matches && node.matches(selectorConfig.selector)) {
                if (!node._scrollTrackingObserved) {
                  observer.observe(node);
                  node._scrollTrackingObserved = true;
                }
              }
              
              // Check children
              const childElements = node.querySelectorAll ? node.querySelectorAll(selectorConfig.selector) : [];
              childElements.forEach(child => {
                if (!child._scrollTrackingObserved) {
                  observer.observe(child);
                  child._scrollTrackingObserved = true;
                }
              });
            });
          }
        });
      });
    });
    
    mutationObserver.observe(document.body, {
      childList: true,
      subtree: true
    });
    
    // Store mutation observer for cleanup
    observer._mutationObserver = mutationObserver;
  }
  
  return observer;
}


/**
 * Initialize scroll tracking
 */
function initializeScrollTracking(userConfig = {}) {
  // Only run on client side and prevent duplicate initialization
  if (!ExecutionEnvironment.canUseDOM || isScrollTrackingInitialized) return;
  
  // Merge default config with injected config and user config
  const injectedConfig = window.__SCROLL_TRACKING_CONFIG__ || {};
  const config = { ...defaultConfig, ...injectedConfig, ...userConfig };
  
  // Set up element intersection tracking
  const observer = setupElementTracking(config);
  
  // Mark as initialized
  isScrollTrackingInitialized = true;
  
  // Store observer for cleanup
  window._scrollTrackingObserver = observer;
}

/**
 * Cleanup scroll tracking
 */
function cleanupScrollTracking() {
  if (window._scrollTrackingObserver) {
    // Clean up mutation observer
    if (window._scrollTrackingObserver._mutationObserver) {
      window._scrollTrackingObserver._mutationObserver.disconnect();
    }
    
    // Clean up intersection observer
    window._scrollTrackingObserver.disconnect();
    window._scrollTrackingObserver = null;
  }
  
  // Clear tracking flags from elements
  document.querySelectorAll('[data-scroll-tracked]').forEach(el => {
    delete el._scrollTrackingObserved;
    el.removeAttribute('data-scroll-tracked');
  });
  
  isScrollTrackingInitialized = false;
}

// Initialize on DOM ready
if (ExecutionEnvironment.canUseDOM) {
  // Function to ensure DOM is fully ready before initializing
  const initWhenReady = () => {
    // Wait a bit longer to ensure all content is rendered
    setTimeout(() => {
      initializeScrollTracking();
    }, 250);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWhenReady);
  } else if (document.readyState === 'interactive') {
    // DOM is loaded but resources might still be loading
    setTimeout(initWhenReady, 100);
  } else {
    // Document is fully loaded
    initWhenReady();
  }
  
  // Re-initialize on route changes for SPA navigation
  window.addEventListener('popstate', () => {
    cleanupScrollTracking();
    setTimeout(() => initializeScrollTracking(), 100);
  });
}

// Export for route change handling
export function onRouteDidUpdate({location, previousLocation}) {
  if (
    ExecutionEnvironment.canUseDOM &&
    previousLocation &&
    location.pathname !== previousLocation.pathname
  ) {
    cleanupScrollTracking();
    setTimeout(() => initializeScrollTracking(), 100);
  }
}