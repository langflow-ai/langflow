import {
  getAllChatInputNodeIds,
  getAllFileNodeIds,
  getChatInputNodeId,
  getFileNodeId,
  getNonFileTypeTweaks,
  hasChatInputFiles,
  hasFileTweaks,
} from "../detect-file-tweaks";
import { getNewCurlCode } from "../get-curl-code";
import { getNewJsApiCode } from "../get-js-api-code";
import { getNewPythonApiCode } from "../get-python-api-code";

describe("API Snippet Generation Utilities", () => {
  describe("File Tweak Detection", () => {
    it("should detect File path array", () => {
      expect(hasFileTweaks({ node1: { path: [] } })).toBe(true);
    });

    it("should detect VideoFile file_path string", () => {
      expect(hasFileTweaks({ node2: { file_path: "path" } })).toBe(true);
    });

    it("should detect ChatInput files string", () => {
      expect(hasFileTweaks({ node3: { files: "path" } })).toBe(true);
    });

    it("should return false for no files", () => {
      expect(hasFileTweaks({ node: { other: "value" } })).toBe(false);
    });

    it("should detect ChatInput files specifically", () => {
      expect(hasChatInputFiles({ node: { files: "path" } })).toBe(true);
      expect(hasChatInputFiles({ node: { path: [] } })).toBe(false);
    });

    it("should get single ChatInput node ID", () => {
      expect(getChatInputNodeId({ node1: { files: "path" } })).toBe("node1");
      expect(getChatInputNodeId({ node1: { other: "value" } })).toBeNull();
    });

    it("should get single File node ID", () => {
      expect(getFileNodeId({ node1: { path: [] } })).toBe("node1");
      expect(getFileNodeId({ node1: { file_path: "path" } })).toBe("node1");
      expect(getFileNodeId({ node1: { files: "path" } })).toBeNull();
    });

    it("should get all ChatInput node IDs", () => {
      expect(
        getAllChatInputNodeIds({
          node1: { files: "p1" },
          node2: { files: "p2" },
          node3: { other: "v" },
        }),
      ).toEqual(["node1", "node2"]);
    });

    it("should get all File and VideoFile node IDs", () => {
      expect(
        getAllFileNodeIds({
          node1: { path: [] },
          node2: { file_path: "p" },
          node3: { files: "p" },
          node4: { other: "v" },
        }),
      ).toEqual(["node1", "node2"]);
    });

    it("should filter out file-related tweaks", () => {
      const tweaks = {
        node1: { path: [] },
        node2: { file_path: "p" },
        node3: { files: "p" },
        node4: { other: "value" },
        node5: { param: 123 },
      };
      const result = getNonFileTypeTweaks(tweaks);
      expect(result).toEqual({
        node4: { other: "value" },
        node5: { param: 123 },
      });
    });
  });

  describe("API Code Generation", () => {
    const baseOptions = {
      flowId: "test-flow-id",
      endpointName: "test-endpoint",
      processedPayload: {
        output_type: "chat",
        input_type: "chat",
        input_value: "Hello",
      },
      shouldDisplayApiKey: true,
    };

    const noAuthOptions = {
      ...baseOptions,
      shouldDisplayApiKey: false,
    };

    describe("Python Code Generation", () => {
      it("should generate basic Python code with API key authentication", () => {
        const code = getNewPythonApiCode(baseOptions);

        // Check for required imports
        expect(code).toContain("import requests");
        expect(code).toContain("import uuid");

        // Check for API key
        expect(code).toContain("api_key = 'YOUR_API_KEY_HERE'");
        expect(code).toContain('headers = {"x-api-key": api_key}');

        // Check for session_id
        expect(code).toContain('payload["session_id"] = str(uuid.uuid4())');

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate basic Python code without API key authentication", () => {
        const code = getNewPythonApiCode(noAuthOptions);

        // Check for required imports
        expect(code).toContain("import requests");
        expect(code).toContain("import uuid");

        // Should not contain API key
        expect(code).not.toContain("api_key = 'YOUR_API_KEY_HERE'");
        expect(code).not.toContain('headers = {"x-api-key": api_key}');

        // Check for session_id
        expect(code).toContain('payload["session_id"] = str(uuid.uuid4())');

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate multi-step code for file uploads with authentication", () => {
        const optionsWithFiles = {
          ...baseOptions,
          processedPayload: {
            ...baseOptions.processedPayload,
            tweaks: {
              node1: { files: "chat_input.txt" },
              node2: { path: ["file.pdf"] },
            },
          },
        };

        const code = getNewPythonApiCode(optionsWithFiles);

        // Check for API key in file upload sections
        expect(code).toContain("api_key = 'YOUR_API_KEY_HERE'");
        expect(code).toContain('headers = {"x-api-key": api_key}');

        // Check for file upload steps
        expect(code).toContain("/api/v1/files/upload/");
        expect(code).toContain("/api/v2/files");
        expect(code).toContain("with open");
        expect(code).toContain('files={"file": f}');
      });

      it("should generate multi-step code for file uploads without authentication", () => {
        const optionsWithFiles = {
          ...noAuthOptions,
          processedPayload: {
            ...noAuthOptions.processedPayload,
            tweaks: {
              node1: { files: "chat_input.txt" },
              node2: { path: ["file.pdf"] },
            },
          },
        };

        const code = getNewPythonApiCode(optionsWithFiles);

        // Should not contain API key
        expect(code).not.toContain("api_key = 'YOUR_API_KEY_HERE'");

        // Check for file upload steps
        expect(code).toContain("/api/v1/files/upload/");
        expect(code).toContain("/api/v2/files");
        expect(code).toContain("with open");
        expect(code).toContain('files={"file": f}');
      });
    });

    describe("JavaScript Code Generation", () => {
      it("should generate basic JavaScript code with API key authentication", () => {
        const code = getNewJsApiCode(baseOptions);

        // Check for API key
        expect(code).toContain("const apiKey = 'YOUR_API_KEY_HERE'");
        expect(code).toContain('"x-api-key": apiKey');

        // Check for session_id
        expect(code).toContain("session_id");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate basic JavaScript code without API key authentication", () => {
        const code = getNewJsApiCode(noAuthOptions);

        // Should not contain API key
        expect(code).not.toContain("const apiKey = 'YOUR_API_KEY_HERE'");
        expect(code).not.toContain("'x-api-key': apiKey");

        // Check for session_id
        expect(code).toContain("session_id");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate multi-step code for file uploads with authentication", () => {
        const optionsWithFiles = {
          ...baseOptions,
          processedPayload: {
            ...baseOptions.processedPayload,
            tweaks: {
              node1: { files: "chat_input.txt" },
              node2: { path: ["file.pdf"] },
            },
          },
        };

        const code = getNewJsApiCode(optionsWithFiles);

        // Check for required modules
        expect(code).toContain("const fs = require('fs')");
        expect(code).toContain(
          "httpModule = protocol === 'https:' ? require('https') : require('http')",
        );

        // Check for API key
        expect(code).toContain("const apiKey = 'YOUR_API_KEY_HERE'");
        expect(code).toContain("const authHeaders = { 'x-api-key': apiKey }");

        // Check for file upload functions
        expect(code).toContain("createFormData");
        expect(code).toContain("makeRequest");

        // Check for upload steps
        expect(code).toContain("/api/v1/files/upload/");
        expect(code).toContain("/api/v2/files");
      });

      it("should generate multi-step code for file uploads without authentication", () => {
        const optionsWithFiles = {
          ...noAuthOptions,
          processedPayload: {
            ...noAuthOptions.processedPayload,
            tweaks: {
              node1: { files: "chat_input.txt" },
              node2: { path: ["file.pdf"] },
            },
          },
        };

        const code = getNewJsApiCode(optionsWithFiles);

        // Check for required modules
        expect(code).toContain("const fs = require('fs')");
        expect(code).toContain(
          "httpModule = protocol === 'https:' ? require('https') : require('http')",
        );

        // Should not contain API key
        expect(code).not.toContain("const apiKey = 'YOUR_API_KEY_HERE'");

        // Check for file upload functions
        expect(code).toContain("createFormData");
        expect(code).toContain("makeRequest");

        // Check for upload steps
        expect(code).toContain("/api/v1/files/upload/");
        expect(code).toContain("/api/v2/files");
      });
    });

    describe("cURL Code Generation", () => {
      it("should generate Unix cURL code with API key authentication", () => {
        const code = getNewCurlCode({ ...baseOptions, platform: "unix" });

        // Check for API key
        expect(code).toContain("x-api-key: YOUR_API_KEY_HERE");

        // Check for session_id placeholder
        expect(code).toContain("YOUR_SESSION_ID_HERE");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate Unix cURL code without API key authentication", () => {
        const code = getNewCurlCode({ ...noAuthOptions, platform: "unix" });

        // Should not contain API key
        expect(code).not.toContain("x-api-key: YOUR_API_KEY_HERE");

        // Check for session_id placeholder
        expect(code).toContain("YOUR_SESSION_ID_HERE");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate PowerShell cURL code with API key authentication", () => {
        const code = getNewCurlCode({ ...baseOptions, platform: "powershell" });

        // Check for API key
        expect(code).toContain('--header "x-api-key: YOUR_API_KEY_HERE"');

        // Check for session_id placeholder
        expect(code).toContain("YOUR_SESSION_ID_HERE");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate PowerShell cURL code without API key authentication", () => {
        const code = getNewCurlCode({
          ...noAuthOptions,
          platform: "powershell",
        });

        // Should not contain API key
        expect(code).not.toContain('--header "x-api-key: YOUR_API_KEY_HERE"');

        // Check for session_id placeholder
        expect(code).toContain("YOUR_SESSION_ID_HERE");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate multi-step code for file uploads with authentication", () => {
        const optionsWithFiles = {
          ...baseOptions,
          processedPayload: {
            ...baseOptions.processedPayload,
            tweaks: {
              node1: { files: "chat_input.txt" },
              node2: { path: ["file.pdf"] },
            },
          },
        };

        const result = getNewCurlCode({
          ...optionsWithFiles,
          platform: "unix",
        }) as { steps: { title: string; code: string }[] };

        // Check that it returns structured steps
        expect(result).toHaveProperty("steps");
        expect(Array.isArray(result.steps)).toBe(true);
        expect(result.steps).toHaveLength(2);

        // Check step 1 (upload files)
        expect(result.steps[0]).toHaveProperty("title");
        expect(result.steps[0].title).toContain("Upload files");
        expect(result.steps[0]).toHaveProperty("code");
        expect(result.steps[0].code).toContain("/api/v1/files/upload/");
        expect(result.steps[0].code).toContain("/api/v2/files");
        expect(result.steps[0].code).toContain('--form "file=@');
        expect(result.steps[0].code).toContain("x-api-key: YOUR_API_KEY_HERE");

        // Check step 2 (execute flow)
        expect(result.steps[1]).toHaveProperty("title");
        expect(result.steps[1].title).toContain("Execute");
        expect(result.steps[1]).toHaveProperty("code");
        expect(result.steps[1].code).toContain("/api/v1/run/test-endpoint");
        expect(result.steps[1].code).toContain("x-api-key: YOUR_API_KEY_HERE");
      });

      it("should generate multi-step code for file uploads without authentication", () => {
        const optionsWithFiles = {
          ...noAuthOptions,
          processedPayload: {
            ...noAuthOptions.processedPayload,
            tweaks: {
              node1: { files: "chat_input.txt" },
              node2: { path: ["file.pdf"] },
            },
          },
        };

        const result = getNewCurlCode({
          ...optionsWithFiles,
          platform: "unix",
        }) as { steps: { title: string; code: string }[] };

        // Check that it returns structured steps
        expect(result).toHaveProperty("steps");
        expect(Array.isArray(result.steps)).toBe(true);
        expect(result.steps).toHaveLength(2);

        // Check step 1 (upload files) - should not contain API key
        expect(result.steps[0]).toHaveProperty("title");
        expect(result.steps[0].title).toContain("Upload files");
        expect(result.steps[0]).toHaveProperty("code");
        expect(result.steps[0].code).toContain("/api/v1/files/upload/");
        expect(result.steps[0].code).toContain("/api/v2/files");
        expect(result.steps[0].code).toContain('--form "file=@');
        expect(result.steps[0].code).not.toContain(
          "x-api-key: YOUR_API_KEY_HERE",
        );

        // Check step 2 (execute flow) - should not contain API key
        expect(result.steps[1]).toHaveProperty("title");
        expect(result.steps[1].title).toContain("Execute");
        expect(result.steps[1]).toHaveProperty("code");
        expect(result.steps[1].code).toContain("/api/v1/run/test-endpoint");
        expect(result.steps[1].code).not.toContain(
          "x-api-key: YOUR_API_KEY_HERE",
        );
      });
    });

    describe("Common Features", () => {
      it("should conditionally include API key based on shouldDisplayApiKey parameter", () => {
        const pythonCodeAuth = getNewPythonApiCode(baseOptions);
        const pythonCodeNoAuth = getNewPythonApiCode(noAuthOptions);
        const jsCodeAuth = getNewJsApiCode(baseOptions);
        const jsCodeNoAuth = getNewJsApiCode(noAuthOptions);
        const curlResultAuth = getNewCurlCode(baseOptions);
        const curlResultNoAuth = getNewCurlCode(noAuthOptions);

        // With authentication
        expect(pythonCodeAuth).toContain("YOUR_API_KEY_HERE");
        expect(jsCodeAuth).toContain("YOUR_API_KEY_HERE");
        expect(curlResultAuth).toContain("YOUR_API_KEY_HERE");

        // Without authentication
        expect(pythonCodeNoAuth).not.toContain("YOUR_API_KEY_HERE");
        expect(jsCodeNoAuth).not.toContain("YOUR_API_KEY_HERE");
        expect(curlResultNoAuth).not.toContain("YOUR_API_KEY_HERE");
      });

      it("should include session_id in all generators", () => {
        const pythonCode = getNewPythonApiCode(baseOptions);
        const jsCode = getNewJsApiCode(baseOptions);
        const curlResult = getNewCurlCode(baseOptions);

        expect(pythonCode).toContain("session_id");
        expect(jsCode).toContain("session_id");

        // Handle both string and object return types for cURL
        if (typeof curlResult === "string") {
          expect(curlResult).toContain("session_id");
        } else {
          // For steps object, check that at least one step contains session_id
          const hasSessionId = curlResult.steps.some((step) =>
            step.code.includes("session_id"),
          );
          expect(hasSessionId).toBe(true);
        }
      });

      it("should handle empty tweaks correctly", () => {
        const optionsWithEmptyTweaks = {
          ...baseOptions,
          processedPayload: {
            ...baseOptions.processedPayload,
            tweaks: {},
          },
        };

        const pythonCode = getNewPythonApiCode(optionsWithEmptyTweaks);
        const jsCode = getNewJsApiCode(optionsWithEmptyTweaks);
        const curlCode = getNewCurlCode(optionsWithEmptyTweaks);

        // Should not generate file upload steps
        expect(pythonCode).not.toContain("Step 1:");
        expect(jsCode).not.toContain("Step 1:");
        // cURL should return string, not steps object
        expect(typeof curlCode).toBe("string");
      });
    });
  });
});
