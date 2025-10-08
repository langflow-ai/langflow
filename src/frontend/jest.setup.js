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

// Mock environment configuration modules to avoid import.meta issues
jest.mock("@/config/env/index", () => ({
  __esModule: true,
  envConfig: {
    backendUrl: "http://localhost:7860",
    apiPrefix: "/api/v1",
    appTitle: "AI Studio",
    buildVersion: "test",
    enableChat: true,
    enableAgentBuilder: true,
    enableHealthcareComponents: true,
    debugMode: false,
    logLevel: "info",
    websocketUrl: "ws://localhost:7860",
    maxFileSize: "10MB",
    timeout: "5000",
    proxyTarget: "http://localhost:7860",
    port: "3000",
  },
  validateEnv: jest.fn((env) => ({
    viteBackendUrl: env.VITE_BACKEND_URL || "http://localhost:7860",
    viteApiPrefix: env.VITE_API_PREFIX || "/api/v1",
    viteAppTitle: env.VITE_APP_TITLE || "AI Studio",
    viteBuildVersion: env.VITE_BUILD_VERSION || "test",
    viteEnableChat: env.VITE_ENABLE_CHAT ? env.VITE_ENABLE_CHAT.toLowerCase() === "true" : true,
    viteEnableAgentBuilder: env.VITE_ENABLE_AGENT_BUILDER ? env.VITE_ENABLE_AGENT_BUILDER.toLowerCase() === "true" : true,
    viteEnableHealthcareComponents: env.VITE_ENABLE_HEALTHCARE_COMPONENTS ? env.VITE_ENABLE_HEALTHCARE_COMPONENTS.toLowerCase() === "true" : true,
    viteDebugMode: env.VITE_DEBUG_MODE ? env.VITE_DEBUG_MODE.toLowerCase() === "true" : false,
    viteLogLevel: env.VITE_LOG_LEVEL || "info",
  })),
}));

jest.mock("@/config/constants", () => ({
  __esModule: true,
  getBackendUrl: () => "http://localhost:7860",
  getApiPrefix: () => "/api/v1",
  getWebSocketUrl: () => "ws://localhost:7860",
  BASE_URL_API: "http://localhost:7860/api/v1/",
  BASE_URL_API_V2: "http://localhost:7860/api/v2/",
  APP_CONFIG: {
    title: "AI Studio",
    buildVersion: "test",
    debugMode: false,
    logLevel: "info",
  },
  FEATURE_FLAGS: {
    enableChat: true,
    enableAgentBuilder: true,
    enableHealthcareComponents: true,
  },
  ADVANCED_CONFIG: {
    maxFileSize: "10MB",
    timeout: 5000,
  },
  PROXY_CONFIG: {
    target: "http://localhost:7860",
    port: 3000,
  },
}));
