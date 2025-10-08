import { validateEnv, envConfig } from "../env/index";
import { ZodError } from "zod";

// Mock window object for browser environment simulation
const mockWindow = {
  _env_: {},
};

Object.defineProperty(global, "window", {
  value: mockWindow,
  writable: true,
});

// Mock import.meta.env for development environment simulation
const mockImportMeta = {
  env: {
    DEV: false,
    VITE_BACKEND_URL: "",
    VITE_API_PREFIX: "",
    VITE_APP_TITLE: "",
    VITE_BUILD_VERSION: "",
    VITE_ENABLE_CHAT: "",
    VITE_ENABLE_AGENT_BUILDER: "",
    VITE_ENABLE_HEALTHCARE_COMPONENTS: "",
    VITE_DEBUG_MODE: "",
    VITE_LOG_LEVEL: "",
    VITE_WEBSOCKET_URL: "",
    VITE_MAX_FILE_SIZE: "",
    VITE_TIMEOUT: "",
  },
};

describe("Environment Configuration", () => {
  beforeEach(() => {
    // Reset mocks before each test
    mockWindow._env_ = {};
    mockImportMeta.env = {
      DEV: false,
      VITE_BACKEND_URL: "",
      VITE_API_PREFIX: "",
      VITE_APP_TITLE: "",
      VITE_BUILD_VERSION: "",
      VITE_ENABLE_CHAT: "",
      VITE_ENABLE_AGENT_BUILDER: "",
      VITE_ENABLE_HEALTHCARE_COMPONENTS: "",
      VITE_DEBUG_MODE: "",
      VITE_LOG_LEVEL: "",
      VITE_WEBSOCKET_URL: "",
      VITE_MAX_FILE_SIZE: "",
      VITE_TIMEOUT: "",
    };

    // Clear import.meta mock
    if (global.importMeta) {
      delete global.importMeta;
    }
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe("validateEnv", () => {
    it("should validate and transform valid environment variables", () => {
      const validEnv = {
        VITE_BACKEND_URL: "https://api.example.com",
        VITE_API_PREFIX: "/api/v1",
        VITE_APP_TITLE: "Test Studio",
        VITE_BUILD_VERSION: "1.0.0",
        VITE_ENABLE_CHAT: "true",
        VITE_ENABLE_AGENT_BUILDER: "false",
        VITE_ENABLE_HEALTHCARE_COMPONENTS: "true",
        VITE_DEBUG_MODE: "false",
        VITE_LOG_LEVEL: "info",
        VITE_WEBSOCKET_URL: "wss://ws.example.com",
        VITE_MAX_FILE_SIZE: "10MB",
        VITE_TIMEOUT: "5000",
      };

      const result = validateEnv(validEnv);

      expect(result).toEqual({
        viteBackendUrl: "https://api.example.com",
        viteApiPrefix: "/api/v1",
        viteAppTitle: "Test Studio",
        viteBuildVersion: "1.0.0",
        viteEnableChat: true,
        viteEnableAgentBuilder: false,
        viteEnableHealthcareComponents: true,
        viteDebugMode: false,
        viteLogLevel: "info",
        viteWebsocketUrl: "wss://ws.example.com",
        viteMaxFileSize: "10MB",
        viteTimeout: "5000",
      });
    });

    it("should apply default values for optional fields", () => {
      const minimalEnv = {
        VITE_BACKEND_URL: "https://api.example.com",
      };

      const result = validateEnv(minimalEnv);

      expect(result.viteBackendUrl).toBe("https://api.example.com");
      expect(result.viteApiPrefix).toBe("/api/v1");
      expect(result.viteAppTitle).toBe("AI Studio");
      expect(result.viteEnableChat).toBe(true);
      expect(result.viteEnableAgentBuilder).toBe(true);
      expect(result.viteEnableHealthcareComponents).toBe(true);
      expect(result.viteDebugMode).toBe(false);
      expect(result.viteLogLevel).toBe("info");
    });

    it("should throw ZodError for invalid URL", () => {
      const invalidEnv = {
        VITE_BACKEND_URL: "not-a-valid-url",
      };

      expect(() => validateEnv(invalidEnv)).toThrow(ZodError);
    });

    it("should throw ZodError for missing required fields", () => {
      const emptyEnv = {};

      expect(() => validateEnv(emptyEnv)).toThrow(ZodError);
    });

    it("should convert boolean strings correctly", () => {
      const booleanTestEnv = {
        VITE_BACKEND_URL: "https://api.example.com",
        VITE_ENABLE_CHAT: "TRUE",
        VITE_ENABLE_AGENT_BUILDER: "False",
        VITE_ENABLE_HEALTHCARE_COMPONENTS: "true",
        VITE_DEBUG_MODE: "FALSE",
      };

      const result = validateEnv(booleanTestEnv);

      expect(result.viteEnableChat).toBe(true);
      expect(result.viteEnableAgentBuilder).toBe(false);
      expect(result.viteEnableHealthcareComponents).toBe(true);
      expect(result.viteDebugMode).toBe(false);
    });

    it("should handle camelCase conversion correctly", () => {
      const env = {
        VITE_BACKEND_URL: "https://api.example.com",
        VITE_API_PREFIX: "/api/v2",
        VITE_MAX_FILE_SIZE: "50MB",
        VITE_WEBSOCKET_URL: "wss://ws.example.com",
      };

      const result = validateEnv(env);

      expect(result).toHaveProperty("viteBackendUrl");
      expect(result).toHaveProperty("viteApiPrefix");
      expect(result).toHaveProperty("viteMaxFileSize");
      expect(result).toHaveProperty("viteWebsocketUrl");
      expect(result.viteBackendUrl).toBe("https://api.example.com");
      expect(result.viteApiPrefix).toBe("/api/v2");
    });
  });

  describe("envConfig runtime integration", () => {
    it("should use window._env_ in production environment", () => {
      // Simulate production environment with window._env_
      mockWindow._env_ = {
        VITE_BACKEND_URL: "https://prod-api.example.com",
        VITE_API_PREFIX: "/api/v1",
        VITE_APP_TITLE: "Production Studio",
        VITE_ENABLE_CHAT: "true",
        VITE_DEBUG_MODE: "false",
      };

      // Mock typeof window !== "undefined" (production)
      Object.defineProperty(global, "window", {
        value: mockWindow,
        writable: true,
      });

      // Re-import to get fresh instance
      jest.resetModules();
      const { envConfig: freshEnvConfig } = require("../env/index");

      expect(freshEnvConfig.backendUrl).toBe("https://prod-api.example.com");
      expect(freshEnvConfig.appTitle).toBe("Production Studio");
      expect(freshEnvConfig.enableChat).toBe(true);
      expect(freshEnvConfig.debugMode).toBe(false);
    });

    it("should handle missing window._env_ gracefully", () => {
      // Simulate production environment without window._env_
      const windowWithoutEnv = {} as any;

      Object.defineProperty(global, "window", {
        value: windowWithoutEnv,
        writable: true,
      });

      // Re-import to get fresh instance
      jest.resetModules();

      // This should not throw but should handle the missing environment gracefully
      expect(() => {
        const { envConfig: freshEnvConfig } = require("../env/index");
        // Should have default values
        expect(freshEnvConfig.appTitle).toBeDefined();
      }).not.toThrow();
    });

    it("should provide sensible defaults when environment is incomplete", () => {
      mockWindow._env_ = {
        VITE_BACKEND_URL: "https://api.example.com",
        // Missing other values
      };

      jest.resetModules();
      const { envConfig: freshEnvConfig } = require("../env/index");

      expect(freshEnvConfig.backendUrl).toBe("https://api.example.com");
      expect(freshEnvConfig.apiPrefix).toBe("/api/v1"); // default
      expect(freshEnvConfig.appTitle).toBe("AI Studio"); // default
      expect(freshEnvConfig.enableChat).toBe(true); // default
    });
  });

  describe("error handling", () => {
    it("should handle ZodError gracefully and provide fallback", () => {
      // Simulate invalid environment that would cause Zod error
      mockWindow._env_ = {
        VITE_BACKEND_URL: "invalid-url",
        VITE_ENABLE_CHAT: "invalid-boolean",
      };

      jest.resetModules();

      // Should not crash the application
      expect(() => {
        const { envConfig: freshEnvConfig } = require("../env/index");
        // Should provide some fallback values
        expect(freshEnvConfig).toBeDefined();
      }).not.toThrow();
    });

    it("should log validation errors in development", () => {
      const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

      mockWindow._env_ = {
        VITE_BACKEND_URL: "invalid-url",
      };

      jest.resetModules();
      const { envConfig: freshEnvConfig } = require("../env/index");

      // Should have logged the error
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });

  describe("type safety", () => {
    it("should export correct TypeScript types", () => {
      const validEnv = {
        VITE_BACKEND_URL: "https://api.example.com",
        VITE_ENABLE_CHAT: "true",
      };

      const result = validateEnv(validEnv);

      // These should be type-safe assignments
      const backendUrl: string = result.viteBackendUrl;
      const enableChat: boolean = result.viteEnableChat;

      expect(typeof backendUrl).toBe("string");
      expect(typeof enableChat).toBe("boolean");
    });
  });
});