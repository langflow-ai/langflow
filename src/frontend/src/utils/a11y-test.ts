import { configureAxe } from "jest-axe";

// Shared axe instance for component-level a11y unit tests.
// color-contrast requires real layout and canvas, which jsdom cannot provide,
// so contrast stays covered by the page-level IBM checker scans instead.
export const axe = configureAxe({
  rules: {
    "color-contrast": { enabled: false },
  },
});
