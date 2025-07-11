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
    };

    describe("Python Code Generation", () => {
      it("should generate basic Python code without files", () => {
        const code = getNewPythonApiCode(baseOptions);

        // Check for required imports
        expect(code).toContain("import requests");
        expect(code).toContain("import uuid");

        // Check for API key
        expect(code).toContain("api_key = 'YOUR_API_KEY_HERE'");

        // Check for session_id
        expect(code).toContain('payload["session_id"] = str(uuid.uuid4())');

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate multi-step code for file uploads", () => {
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

        // Check for file upload steps
        expect(code).toContain("/api/v1/files/upload/");
        expect(code).toContain("/api/v2/files");
        expect(code).toContain("with open");
        expect(code).toContain('files={"file": f}');
      });
    });

    describe("JavaScript Code Generation", () => {
      it("should generate basic JavaScript code without files", () => {
        const code = getNewJsApiCode(baseOptions);

        // Check for API key
        expect(code).toContain("const apiKey = 'YOUR_API_KEY_HERE'");

        // Check for session_id (it's generated server-side, so just check it exists)
        expect(code).toContain("session_id");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate multi-step code for file uploads", () => {
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
        expect(code).toContain("const http = require('http')");

        // Check for file upload functions
        expect(code).toContain("createFormData");
        expect(code).toContain("makeRequest");

        // Check for upload steps
        expect(code).toContain("/api/v1/files/upload/");
        expect(code).toContain("/api/v2/files");
      });
    });

    describe("cURL Code Generation", () => {
      it("should generate Unix cURL code without files", () => {
        const code = getNewCurlCode({ ...baseOptions, platform: "unix" });

        // Check for API key (quotes may vary)
        expect(code).toContain("x-api-key: YOUR_API_KEY_HERE");

        // Check for session_id with Unix UUID generation
        expect(code).toContain(
          "$(uuidgen || cat /proc/sys/kernel/random/uuid)",
        );

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate PowerShell cURL code without files", () => {
        const code = getNewCurlCode({ ...baseOptions, platform: "powershell" });

        // Check for API key
        expect(code).toContain('--header "x-api-key: YOUR_API_KEY_HERE"');

        // Check for session_id with PowerShell UUID generation
        expect(code).toContain("$(New-Guid).Guid");

        // Check for correct endpoint
        expect(code).toContain("/api/v1/run/test-endpoint");
      });

      it("should generate multi-step code for file uploads", () => {
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

        const code = getNewCurlCode({ ...optionsWithFiles, platform: "unix" });

        // Check for step markers
        expect(code).toContain("##STEP1_START##");
        expect(code).toContain("##STEP1_END##");
        expect(code).toContain("##STEP2_START##");
        expect(code).toContain("##STEP2_END##");

        // Check for file upload commands
        expect(code).toContain("/api/v1/files/upload/");
        expect(code).toContain("/api/v2/files");
        expect(code).toContain('-F "file=@');
      });
    });

    describe("Common Features", () => {
      it("should always include API key in all generators", () => {
        const pythonCode = getNewPythonApiCode(baseOptions);
        const jsCode = getNewJsApiCode(baseOptions);
        const curlCode = getNewCurlCode(baseOptions);

        expect(pythonCode).toContain("YOUR_API_KEY_HERE");
        expect(jsCode).toContain("YOUR_API_KEY_HERE");
        expect(curlCode).toContain("YOUR_API_KEY_HERE");
      });

      it("should include session_id in all generators", () => {
        const pythonCode = getNewPythonApiCode(baseOptions);
        const jsCode = getNewJsApiCode(baseOptions);
        const curlCode = getNewCurlCode(baseOptions);

        expect(pythonCode).toContain("session_id");
        expect(jsCode).toContain("session_id");
        expect(curlCode).toContain("session_id");
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
        expect(curlCode).not.toContain("##STEP1_START##");
      });
    });
  });
});
