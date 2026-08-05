module.exports = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  coverageProvider: "v8",
  injectGlobals: true,
  moduleNameMapper: {
    "\\.(css|less|scss|sass)$": "<rootDir>/src/__mocks__/styleMock.js",
    "^@/(.*)$": "<rootDir>/src/$1",
    "^@jsonquerylang/jsonquery$":
      "<rootDir>/src/__mocks__/@jsonquerylang/jsonquery.js",
    "^vanilla-jsoneditor$": "<rootDir>/src/__mocks__/vanilla-jsoneditor.js",
    "^uuid$": "<rootDir>/src/__mocks__/uuid.js",
  },
  setupFilesAfterEnv: ["<rootDir>/src/setupTests.ts"],
  setupFiles: ["<rootDir>/jest.setup.js"],
  testMatch: [
    "<rootDir>/src/**/__tests__/**/*.{test,spec}.{ts,tsx}",
    "<rootDir>/src/**/*.{test,spec}.{ts,tsx}",
  ],
  testPathIgnorePatterns: ["/node_modules/", "test-utils.tsx"],
  transform: {
    "^.+\\.(ts|tsx)$": "<rootDir>/transform-import-meta.js",
    // The unified/rehype sanitizer packages are ESM-only, so compile just
    // those to CJS. This lets the markdown sanitization schema be tested
    // against the real `hast-util-sanitize` and the real upstream
    // `defaultSchema` rather than against a mock — mocking `rehype-sanitize`
    // makes `defaultSchema` undefined, which silently degrades the very
    // control under test (see src/utils/__tests__/sanitizeSchema.test.ts).
    //
    // Two constraints keep this narrow, and both are load-bearing:
    //  - It must point at the SAME transformer path with the SAME (empty)
    //    options as the entry above, so Jest reuses one ts-jest instance.
    //    A second, separately-configured ts-jest breaks ts-jest's `jest.mock`
    //    hoisting in .ts/.tsx suites that reference mock variables inside a
    //    `jest.mock` factory.
    //  - It must not match other node_modules (notably @testing-library,
    //    which ships CJS that ts-jest's es5 target miscompiles).
    "node_modules[/\\\\](?:rehype-sanitize|hast-util-sanitize|unist-util-position|@ungap[/\\\\]structured-clone)[/\\\\].+\\.js$":
      "<rootDir>/transform-import-meta.js",
  },
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
  // Ignore node_modules except for packages that need transformation
  transformIgnorePatterns: [
    "node_modules/(?!(.*\\.mjs$|@testing-library|rehype-sanitize|hast-util-sanitize|unist-util-position|@ungap/structured-clone))",
  ],

  // Coverage configuration
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.{test,spec}.{ts,tsx}",
    "!src/**/tests/**",
    "!src/**/__tests__/**",
    "!src/setupTests.ts",
    "!src/vite-env.d.ts",
    "!src/**/*.d.ts",
  ],
  coverageDirectory: "coverage/jest",
  coverageReporters: ["text", "lcov", "html", "json", "json-summary"],
  coveragePathIgnorePatterns: ["/node_modules/", "/tests/"],

  // CI-specific configuration
  ...(process.env.CI === "true" && {
    reporters: [
      "default",
      [
        "jest-junit",
        {
          outputDirectory: "test-results",
          outputName: "junit.xml",
          ancestorSeparator: " › ",
          uniqueOutputName: "false",
          suiteNameTemplate: "{filepath}",
          classNameTemplate: "{classname}",
          titleTemplate: "{title}",
        },
      ],
    ],
    maxWorkers: "50%",
    verbose: true,
  }),
};
