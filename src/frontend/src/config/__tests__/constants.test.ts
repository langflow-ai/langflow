import {
  getBackendUrl,
  getApiPrefix,
  getWebSocketUrl,
  BASE_URL_API,
  BASE_URL_API_V2,
  APP_CONFIG,
  FEATURE_FLAGS,
  ADVANCED_CONFIG,
} from "../constants";

// Mock the env configuration
jest.mock("../env/index", () => ({
  envConfig: {
    backendUrl: "https://test-backend.example.com",
    apiPrefix: "/api/v1",
    appTitle: "Test AI Studio",
    buildVersion: "1.0.0-test",
    debugMode: true,
    logLevel: "debug",
    enableChat: false,
    enableAgentBuilder: true,
    enableHealthcareComponents: false,
    websocketUrl: "wss://test-ws.example.com",
    maxFileSize: "25MB",
    timeout: "10000",
  },
}));

// Mock import.meta.env
const mockImportMeta = {
  env: {
    DEV: false,
  },
};

Object.defineProperty(global, "import", {
  value: {
    meta: mockImportMeta,
  },
  writable: true,
});

describe("Constants Configuration", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("getBackendUrl", () => {
    it("should return backend URL from environment config", () => {
      const url = getBackendUrl();
      expect(url).toBe("https://test-backend.example.com");
    });

    it("should return fallback URL when envConfig.backendUrl is empty", () => {
      // Mock empty backend URL
      jest.doMock("../env/index", () => ({
        envConfig: {
          backendUrl: "",
        },
      }));

      jest.resetModules();
      const { getBackendUrl: freshGetBackendUrl } = require("../constants");
      const url = freshGetBackendUrl();
      expect(url).toBe("http://localhost:7860");
    });

    it("should return empty string in development mode when backendUrl is not set", () => {
      // Mock development environment
      mockImportMeta.env.DEV = true;

      jest.doMock("../env/index", () => ({
        envConfig: {
          backendUrl: "",
        },
      }));

      jest.resetModules();
      const { getBackendUrl: freshGetBackendUrl } = require("../constants");
      const url = freshGetBackendUrl();
      expect(url).toBe("");
    });
  });

  describe("getApiPrefix", () => {
    it("should return API prefix from environment config", () => {
      const prefix = getApiPrefix();
      expect(prefix).toBe("/api/v1");
    });

    it("should return default API prefix when not configured", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          apiPrefix: "",
        },
      }));

      jest.resetModules();
      const { getApiPrefix: freshGetApiPrefix } = require("../constants");
      const prefix = freshGetApiPrefix();
      expect(prefix).toBe("/api/v1");
    });
  });

  describe("getWebSocketUrl", () => {
    it("should return configured WebSocket URL", () => {
      const wsUrl = getWebSocketUrl();
      expect(wsUrl).toBe("wss://test-ws.example.com");
    });

    it("should derive WebSocket URL from backend URL when not explicitly set", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          websocketUrl: "",
          backendUrl: "https://api.example.com",
        },
      }));

      jest.resetModules();
      const { getWebSocketUrl: freshGetWebSocketUrl } = require("../constants");
      const wsUrl = freshGetWebSocketUrl();
      expect(wsUrl).toBe("wss://api.example.com");
    });

    it("should derive WebSocket URL from HTTP backend URL", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          websocketUrl: "",
          backendUrl: "http://localhost:7860",
        },
      }));

      jest.resetModules();
      const { getWebSocketUrl: freshGetWebSocketUrl } = require("../constants");
      const wsUrl = freshGetWebSocketUrl();
      expect(wsUrl).toBe("ws://localhost:7860");
    });

    it("should return undefined when no WebSocket or backend URL is available", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          websocketUrl: "",
          backendUrl: "",
        },
      }));

      jest.resetModules();
      const { getWebSocketUrl: freshGetWebSocketUrl } = require("../constants");
      const wsUrl = freshGetWebSocketUrl();
      expect(wsUrl).toBeUndefined();
    });
  });

  describe("BASE_URL_API", () => {
    it("should construct correct API URL", () => {
      expect(BASE_URL_API).toBe("https://test-backend.example.com/api/v1/");
    });

    it("should handle empty backend URL gracefully", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          backendUrl: "",
          apiPrefix: "/api/v1",
        },
      }));

      jest.resetModules();
      const { BASE_URL_API: freshBaseUrlApi } = require("../constants");
      expect(freshBaseUrlApi).toBe("http://localhost:7860/api/v1/");
    });
  });

  describe("BASE_URL_API_V2", () => {
    it("should construct correct API v2 URL", () => {
      expect(BASE_URL_API_V2).toBe("https://test-backend.example.com/api/v2/");
    });
  });

  describe("APP_CONFIG", () => {
    it("should provide correct app configuration", () => {
      expect(APP_CONFIG).toEqual({
        title: "Test AI Studio",
        buildVersion: "1.0.0-test",
        debugMode: true,
        logLevel: "debug",
      });
    });

    it("should provide default values when environment is not configured", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          appTitle: "",
          buildVersion: "",
          debugMode: "",
          logLevel: "",
        },
      }));

      jest.resetModules();
      const { APP_CONFIG: freshAppConfig } = require("../constants");
      expect(freshAppConfig).toEqual({
        title: "AI Studio",
        buildVersion: "development",
        debugMode: false,
        logLevel: "info",
      });
    });

    it("should be immutable (readonly)", () => {
      expect(() => {
        // @ts-expect-error - testing immutability
        APP_CONFIG.title = "Modified Title";
      }).toThrow();
    });
  });

  describe("FEATURE_FLAGS", () => {
    it("should provide correct feature flags", () => {
      expect(FEATURE_FLAGS).toEqual({
        enableChat: false,
        enableAgentBuilder: true,
        enableHealthcareComponents: false,
      });
    });

    it("should provide default values when not configured", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          enableChat: undefined,
          enableAgentBuilder: undefined,
          enableHealthcareComponents: undefined,
        },
      }));

      jest.resetModules();
      const { FEATURE_FLAGS: freshFeatureFlags } = require("../constants");
      expect(freshFeatureFlags).toEqual({
        enableChat: true,
        enableAgentBuilder: true,
        enableHealthcareComponents: true,
      });
    });

    it("should handle null values correctly", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          enableChat: null,
          enableAgentBuilder: null,
          enableHealthcareComponents: null,
        },
      }));

      jest.resetModules();
      const { FEATURE_FLAGS: freshFeatureFlags } = require("../constants");
      expect(freshFeatureFlags).toEqual({
        enableChat: true,
        enableAgentBuilder: true,
        enableHealthcareComponents: true,
      });
    });

    it("should be immutable (readonly)", () => {
      expect(() => {
        // @ts-expect-error - testing immutability
        FEATURE_FLAGS.enableChat = true;
      }).toThrow();
    });
  });

  describe("ADVANCED_CONFIG", () => {
    it("should provide correct advanced configuration", () => {
      expect(ADVANCED_CONFIG).toEqual({
        maxFileSize: "25MB",
        timeout: 10000, // parsed as integer
      });
    });

    it("should handle undefined values", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          maxFileSize: undefined,
          timeout: undefined,
        },
      }));

      jest.resetModules();
      const { ADVANCED_CONFIG: freshAdvancedConfig } = require("../constants");
      expect(freshAdvancedConfig).toEqual({
        maxFileSize: undefined,
        timeout: undefined,
      });
    });

    it("should parse timeout as integer", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          maxFileSize: "50MB",
          timeout: "15000",
        },
      }));

      jest.resetModules();
      const { ADVANCED_CONFIG: freshAdvancedConfig } = require("../constants");
      expect(freshAdvancedConfig.timeout).toBe(15000);
      expect(typeof freshAdvancedConfig.timeout).toBe("number");
    });

    it("should handle invalid timeout values gracefully", () => {
      jest.doMock("../env/index", () => ({
        envConfig: {
          timeout: "not-a-number",
        },
      }));

      jest.resetModules();
      const { ADVANCED_CONFIG: freshAdvancedConfig } = require("../constants");
      expect(freshAdvancedConfig.timeout).toBeNaN();
    });

    it("should be immutable (readonly)", () => {
      expect(() => {
        // @ts-expect-error - testing immutability
        ADVANCED_CONFIG.maxFileSize = "100MB";
      }).toThrow();
    });
  });

  describe("integration tests", () => {
    it("should work together to provide consistent configuration", () => {
      const backendUrl = getBackendUrl();
      const apiPrefix = getApiPrefix();
      const expectedApiUrl = `${backendUrl}${apiPrefix}/`;

      expect(BASE_URL_API).toBe(expectedApiUrl);
    });

    it("should maintain consistency across all configuration objects", () => {
      // All configuration should come from the same environment source
      expect(typeof getBackendUrl()).toBe("string");
      expect(typeof getApiPrefix()).toBe("string");
      expect(typeof APP_CONFIG.title).toBe("string");
      expect(typeof FEATURE_FLAGS.enableChat).toBe("boolean");
    });
  });
});