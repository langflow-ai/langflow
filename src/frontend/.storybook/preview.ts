import type { Preview } from "@storybook/react";
// Import all CSS files to match the app's styling
import "../src/style/classes.css";
import "../src/style/index.css";
import "../src/App.css";
import "../src/style/applies.css";

const preview: Preview = {
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
