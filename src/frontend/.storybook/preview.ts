import type { Preview } from "@storybook/react-vite";
import * as React from "react";
import { useEffect } from "react";
// Import all CSS files to match the app's styling
import "../src/style/classes.css";
import "../src/style/index.css";
import "../src/App.css";
import "../src/style/applies.css";
import { TooltipProvider } from "../src/components/ui/tooltip";
import { useDarkStore } from "../src/stores/darkStore";

// Global decorator to provide TooltipProvider for all stories
const withTooltipProvider = (Story: React.ComponentType) => {
  const TooltipWrapper = (): React.ReactElement => {
    const storyElement = React.createElement(Story);
    return React.createElement(TooltipProvider, {
      skipDelayDuration: 0,
      children: storyElement,
    });
  };
  return React.createElement(TooltipWrapper);
};

// Global decorator to handle dark mode for all stories
const withTheme = (
  Story: React.ComponentType,
  context: {
    args?: { darkMode?: boolean };
    initialArgs?: { darkMode?: boolean };
    parameters?: { darkMode?: boolean };
    globals?: { theme?: string };
  },
) => {
  const ThemeWrapper = (): React.ReactElement => {
    // Check for dark mode in args, parameters, or globals
    const dark =
      context.args?.darkMode === true ||
      context.initialArgs?.darkMode === true ||
      context.parameters?.darkMode === true ||
      context.globals?.theme === "dark";

    useEffect(() => {
      const bodyElement = document.getElementById("body") || document.body;
      const htmlElement = document.documentElement;

      if (dark) {
        bodyElement.classList.add("dark");
        htmlElement.classList.add("dark");
        useDarkStore.setState({ dark: true });
      } else {
        bodyElement.classList.remove("dark");
        htmlElement.classList.remove("dark");
        useDarkStore.setState({ dark: false });
      }
    }, [dark]);

    // Sync immediately on render
    const bodyElement = document.getElementById("body") || document.body;
    const htmlElement = document.documentElement;
    if (dark) {
      bodyElement.classList.add("dark");
      htmlElement.classList.add("dark");
    } else {
      bodyElement.classList.remove("dark");
      htmlElement.classList.remove("dark");
    }

    return React.createElement(Story);
  };

  return React.createElement(ThemeWrapper);
};

const preview: Preview = {
  decorators: [withTooltipProvider, withTheme],
  parameters: {
    actions: { argTypesRegex: "^on[A-Z].*" },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
