// Jest setup file to mock globals and Vite-specific syntax
const React = require("react");

// Mock react-i18next globally so t(key) returns the English string from en.json
const enTranslations = require("./src/locales/en.json");
const interpolate = (str, params) => {
  if (!params || typeof str !== "string") return str;
  return str.replace(/\{\{(\w+)\}\}/g, (_, k) =>
    k in params ? params[k] : `{{${k}}}`,
  );
};
const resolveKey = (key, params) => {
  if (params && typeof params.count === "number") {
    const suffix = params.count === 1 ? "one" : "other";
    const pluralKey = `${key}_${suffix}`;
    if (enTranslations[pluralKey] !== undefined) return pluralKey;
  }
  return key;
};
// Parse <N>text</N> interpolation tags used by Trans i18nKey values.
const renderTrans = ({ i18nKey, children, components }) => {
  if (!i18nKey || !enTranslations[i18nKey]) return children ?? null;
  const raw = enTranslations[i18nKey];
  if (!components) return raw.replace(/<\d+>([\s\S]*?)<\/\d+>/g, "$1");
  const parts = raw.split(/(<\d+>[\s\S]*?<\/\d+>)/);
  return React.createElement(
    React.Fragment,
    null,
    ...parts.map((part, idx) => {
      const m = part.match(/^<(\d+)>([\s\S]*?)<\/\d+>$/);
      if (m) {
        const comp = components[Number(m[1])];
        if (comp) return React.cloneElement(comp, { key: idx }, m[2]);
        return m[2];
      }
      return part;
    }),
  );
};
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, params) =>
      interpolate(enTranslations[resolveKey(key, params)] ?? key, params),
    i18n: { changeLanguage: jest.fn(), language: "en" },
  }),
  Trans: renderTrans,
  initReactI18next: { type: "3rdParty", init: jest.fn() },
  withTranslation: () => (Component) => Component,
}));

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

// Render children only — tests don't need TooltipProvider context
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }) => children,
}));

// Return empty data — tests don't need QueryClientProvider context
jest.mock("@/controllers/API/queries/flows/use-get-note-translations", () => ({
  useGetNoteTranslationsQuery: () => ({ data: undefined }),
}));

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
