// Jest setup file to mock globals and Vite-specific syntax

// Mock import.meta
global.import = {
  meta: {
    env: {
      CI: process.env.CI || false,
      NODE_ENV: "test",
      MODE: "test",
      DEV: false,
      PROD: false,
      VITE_API_URL: "http://localhost:7860",
    },
  },
};

// Mock crypto for Node.js environment
if (typeof global.crypto === "undefined") {
  const { webcrypto } = require("crypto");
  global.crypto = webcrypto;
}

// Mock URL if not available
if (typeof global.URL === "undefined") {
  global.URL = require("url").URL;
}

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;

// Mock sessionStorage
global.sessionStorage = localStorageMock;

// Polyfill Array.prototype.toSorted for Jest environment if not available
if (!Array.prototype.toSorted) {
  Object.defineProperty(Array.prototype, "toSorted", {
    value: function (compareFn) {
      const copy = this.slice();
      return copy.sort(compareFn);
    },
    writable: true,
    configurable: true,
  });
}

// Global module stubs to avoid ESM/context issues in unit tests
jest.mock("@radix-ui/react-form", () => ({
  __esModule: true,
  Field: (props) => props.children,
  Label: (props) => props.children,
  Control: (props) => props.children,
  Message: (props) => props.children,
  Submit: (props) => props.children,
  Root: (props) => props.children,
}));

jest.mock("react-markdown", () => ({ __esModule: true, default: () => null }));

jest.mock("lucide-react/dynamicIconImports", () => ({}), { virtual: true });

// Avoid darkStore import in tests via genericIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

// Stub custom icon that uses JSX file to avoid transform issues in Jest
jest.mock("@/icons/BotMessageSquare", () => ({
  __esModule: true,
  BotMessageSquareIcon: () => null,
}));

// Provide a minimal import.meta.env shim used in some stores when running under Jest
if (typeof global.import === "undefined") {
  global.import = { meta: { env: { CI: process.env.CI || false } } };
} else if (!global.import.meta) {
  global.import.meta = { env: { CI: process.env.CI || false } };
} else if (!global.import.meta.env) {
  global.import.meta.env = { CI: process.env.CI || false };
}

// Mock darkStore to avoid import.meta usage in modules during tests
jest.mock("@/stores/darkStore", () => ({
  __esModule: true,
  useDarkStore: (selector) =>
    selector
      ? selector({
          dark: false,
          stars: 0,
          version: "",
          latestVersion: "",
          discordCount: 0,
          refreshLatestVersion: () => {},
          setDark: () => {},
          refreshVersion: () => {},
          refreshStars: () => {},
          refreshDiscordCount: () => {},
        })
      : {},
}));
