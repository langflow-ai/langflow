module.exports = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  injectGlobals: true,
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
  },
  setupFilesAfterEnv: ["<rootDir>/src/setupTests.ts"],
  testMatch: [
    "<rootDir>/src/**/__tests__/**/*.{ts,tsx}",
    "<rootDir>/src/**/*.{test,spec}.{ts,tsx}",
  ],
  transform: {
    "^.+\\.(ts|tsx)$": "ts-jest",
  },
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
  // Ignore node_modules except for packages that need transformation
  transformIgnorePatterns: ["node_modules/(?!(.*\\.mjs$|@testing-library))"],

  // Coverage configuration
  collectCoverage: true,
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.{test,spec}.{ts,tsx}",
    "!src/**/tests/**",
    "!src/**/__tests__/**",
    "!src/setupTests.ts",
    "!src/vite-env.d.ts",
    "!src/**/*.d.ts",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["text", "lcov", "html", "json-summary"],
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
