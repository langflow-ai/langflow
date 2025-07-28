module.exports = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  injectGlobals: true,
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
  },
  setupFilesAfterEnv: ["<rootDir>/src/setupTests.ts"],
  setupFiles: ["<rootDir>/jest.setup.js"],
  testMatch: [
    "<rootDir>/src/**/__tests__/**/*.{test,spec}.{ts,tsx}",
    "<rootDir>/src/**/*.{test,spec}.{ts,tsx}",
  ],
  testPathIgnorePatterns: ["/node_modules/", "test-utils.tsx"],
  transform: {
    "^.+\\.(ts|tsx)$": "ts-jest",
  },
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
  // Ignore node_modules except for packages that need transformation
  transformIgnorePatterns: ["node_modules/(?!(.*\\.mjs$|@testing-library))"],

  // Coverage configuration
  collectCoverage: process.env.CI === "true",
  coverageDirectory: "coverage",
  coverageReporters: ["text", "lcov", "html", "json-summary"],
  coveragePathIgnorePatterns: ["/node_modules/", "/tests/"],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },

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
