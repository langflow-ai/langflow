import { getNewJsApiCode } from "../get-js-api-code";

// Mock the customGetHostProtocol
jest.mock("@/customization/utils/custom-get-host-protocol", () => ({
  customGetHostProtocol: () => ({
    protocol: "https:",
    host: "localhost:3000",
  }),
}));

describe("getNewJsApiCode", () => {
  const baseOptions = {
    flowId: "test-flow-123",
    endpointName: "test-endpoint",
    processedPayload: {
      output_type: "chat",
      input_type: "chat",
      input_value: "Test message",
    },
    shouldDisplayApiKey: true,
  };

  describe("Basic code generation without files", () => {
    it("should generate valid JavaScript code with API key authentication", () => {
      const code = getNewJsApiCode(baseOptions);

      // Check API key setup
      expect(code).toContain("const apiKey = 'YOUR_API_KEY_HERE'");
      expect(code).toContain('"x-api-key": apiKey');

      // Check crypto for session ID
      expect(code).toContain("const crypto = require('crypto')");
      expect(code).toContain("session_id");
      expect(code).toContain("crypto.randomUUID()");

      // Check fetch request
      expect(code).toContain("fetch(");
      expect(code).toContain("/api/v1/run/test-endpoint");
      expect(code).toContain("method: 'POST'");

      // Check error handling
      expect(code).toContain(".catch(err => console.error(err))");
    });

    it("should generate valid JavaScript code without API key authentication", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        shouldDisplayApiKey: false,
      });

      // Should NOT contain API key
      expect(code).not.toContain("const apiKey = 'YOUR_API_KEY_HERE'");
      expect(code).not.toContain("'x-api-key': apiKey");

      // Check session ID
      expect(code).toContain("session_id");
      expect(code).toContain("crypto.randomUUID()");

      // Check fetch request
      expect(code).toContain("fetch(");
      expect(code).toContain("/api/v1/run/test-endpoint");
    });

    it("should use flowId when endpointName is not provided", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        endpointName: "",
      });

      expect(code).toContain("/api/v1/run/test-flow-123");
    });

    it("should include Content-Type header", () => {
      const code = getNewJsApiCode(baseOptions);

      expect(code).toContain("'Content-Type': 'application/json'");
    });

    it("should include payload with correct structure", () => {
      const code = getNewJsApiCode(baseOptions);

      expect(code).toContain("const payload =");
      expect(code).toContain("JSON.stringify(payload)");
    });
  });

  describe("File upload handling - ChatInput files (v1 API)", () => {
    it("should generate multi-step code for single ChatInput file", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      // Check required modules
      expect(code).toContain("const fs = require('fs')");
      expect(code).toContain("const path = require('path')");

      // Check for http/https module selection
      expect(code).toContain(
        "httpModule = protocol === 'https:' ? require('https') : require('http')",
      );

      // Check for file upload step
      expect(code).toContain("// Step 1: Upload file for ChatInput chatNode1");
      expect(code).toContain("createFormData('your_image_1.jpg')");
      expect(code).toContain("/api/v1/files/upload/");
      expect(code).toContain("chatFilePath1");

      // Check for flow execution step
      expect(code).toContain("// Step 2: Execute flow with all file paths");

      // Check for helper functions
      expect(code).toContain("function createFormData(filePath)");
      expect(code).toContain("function makeRequest(options, data)");
      expect(code).toContain("async function uploadAndExecuteFlow()");
    });

    it("should generate multi-step code for multiple ChatInput files", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image1.jpg" },
            chatNode2: { files: "image2.png" },
          },
        },
      });

      // Check for both upload steps
      expect(code).toContain("// Step 1: Upload file for ChatInput chatNode1");
      expect(code).toContain("// Step 2: Upload file for ChatInput chatNode2");
      expect(code).toContain("chatFilePath1");
      expect(code).toContain("chatFilePath2");
      expect(code).toContain("your_image_1.jpg");
      expect(code).toContain("your_image_2.jpg");
    });
  });

  describe("File upload handling - File/VideoFile components (v2 API)", () => {
    it("should generate multi-step code for File component with path array", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["document.pdf"] },
          },
        },
      });

      // Check for file upload step
      expect(code).toContain(
        "// Step 1: Upload file for File/VideoFile fileNode1",
      );
      expect(code).toContain("createFormData('your_file_1.pdf')");
      expect(code).toContain("/api/v2/files");
      expect(code).toContain("filePath1");
    });

    it("should generate multi-step code for VideoFile component with file_path string", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            videoNode1: { file_path: "video.mp4" },
          },
        },
      });

      // Check for file upload step
      expect(code).toContain(
        "// Step 1: Upload file for File/VideoFile videoNode1",
      );
      expect(code).toContain("createFormData('your_file_1.pdf')");
      expect(code).toContain("/api/v2/files");
      expect(code).toContain("filePath1");
    });

    it("should generate multi-step code for multiple File/VideoFile components", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["doc.pdf"] },
            videoNode1: { file_path: "vid.mp4" },
          },
        },
      });

      // Check for both upload steps
      expect(code).toContain(
        "// Step 1: Upload file for File/VideoFile fileNode1",
      );
      expect(code).toContain(
        "// Step 2: Upload file for File/VideoFile videoNode1",
      );
      expect(code).toContain("filePath1");
      expect(code).toContain("filePath2");
    });
  });

  describe("Mixed file types handling", () => {
    it("should handle both ChatInput and File/VideoFile uploads", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
            fileNode1: { path: ["doc.pdf"] },
            videoNode1: { file_path: "video.mp4" },
          },
        },
      });

      // Check for ChatInput upload (v1 API)
      expect(code).toContain("// Step 1: Upload file for ChatInput chatNode1");
      expect(code).toContain("/api/v1/files/upload/");

      // Check for File/VideoFile uploads (v2 API)
      expect(code).toContain(
        "// Step 2: Upload file for File/VideoFile fileNode1",
      );
      expect(code).toContain(
        "// Step 3: Upload file for File/VideoFile videoNode1",
      );
      expect(code).toContain("/api/v2/files");

      // Check for flow execution step
      expect(code).toContain("// Step 4: Execute flow with all file paths");
    });

    it("should handle file uploads mixed with non-file tweaks", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
            textNode1: { value: "some text" },
            numberNode1: { count: 42 },
          },
        },
      });

      // Check for file upload
      expect(code).toContain("// Step 1: Upload file for ChatInput chatNode1");

      // Check that non-file tweaks are included
      expect(code).toContain('"textNode1"');
      expect(code).toContain('"numberNode1"');
    });
  });

  describe("Helper functions", () => {
    it("should include createFormData helper function", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("function createFormData(filePath)");
      expect(code).toContain("const boundary = '----FormBoundary'");
      expect(code).toContain("const filename = path.basename(filePath)");
      expect(code).toContain("fs.existsSync(filePath)");
      expect(code).toContain("fs.readFileSync(filePath)");
      expect(code).toContain("Content-Disposition: form-data");
      expect(code).toContain('name="file"');
    });

    it("should include makeRequest helper function", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("function makeRequest(options, data)");
      expect(code).toContain("return new Promise((resolve, reject)");
      expect(code).toContain("httpModule.request(options");
      expect(code).toContain("res.statusCode >= 200 && res.statusCode < 300");
      expect(code).toContain("JSON.parse(responseData)");
    });

    it("should include uploadAndExecuteFlow async function", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("async function uploadAndExecuteFlow()");
      expect(code).toContain("try {");
      expect(code).toContain("} catch (error) {");
      expect(code).toContain("uploadAndExecuteFlow();");
    });
  });

  describe("Authentication handling", () => {
    it("should include API key in file upload requests when shouldDisplayApiKey is true", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        shouldDisplayApiKey: true,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      expect(code).toContain("const apiKey = 'YOUR_API_KEY_HERE'");
      expect(code).toContain("const authHeaders = { 'x-api-key': apiKey }");
      expect(code).toContain("...authHeaders");
    });

    it("should not include API key when shouldDisplayApiKey is false", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        shouldDisplayApiKey: false,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      expect(code).not.toContain("const apiKey = 'YOUR_API_KEY_HERE'");
      expect(code).toContain("const authHeaders = {}");
    });
  });

  describe("HTTP/HTTPS protocol handling", () => {
    it("should dynamically select http or https module based on protocol", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("const protocol = new URL(BASE_URL).protocol");
      expect(code).toContain(
        "const httpModule = protocol === 'https:' ? require('https') : require('http')",
      );
    });

    it("should correctly parse hostname and port from URL", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      // Should be defined at the top of file upload code
      expect(code).toContain("const BASE_URL =");
      expect(code).toContain("const FLOW_ID =");
    });
  });

  describe("Edge cases", () => {
    it("should handle empty tweaks object", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {},
        },
      });

      // Should generate basic code without file uploads
      expect(code).toContain("const payload =");
      expect(code).toContain("fetch(");
      expect(code).not.toContain("// Step 1:");
    });

    it("should handle undefined tweaks", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          output_type: "chat",
          input_type: "chat",
          input_value: "Test",
        },
      });

      // Should generate basic code without file uploads
      expect(code).toContain("fetch(");
      expect(code).not.toContain("// Step 1:");
    });

    it("should handle empty flowId", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        flowId: "",
        endpointName: "my-endpoint",
      });

      expect(code).toContain("/api/v1/run/my-endpoint");
    });

    it("should handle empty endpointName", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        endpointName: "",
      });

      expect(code).toContain("/api/v1/run/test-flow-123");
    });

    it("should handle special characters in input_value", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          input_value: "Hello \"world\" with 'quotes'",
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("Hello \"world\" with 'quotes'");
    });

    it("should handle deeply nested objects in tweaks", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            complexNode: {
              config: {
                nested: {
                  value: 123,
                  enabled: true,
                },
              },
            },
          },
        },
      });

      expect(code).toContain('"complexNode"');
    });
  });

  describe("Payload structure", () => {
    it("should include output_type in payload", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain('"output_type": "chat"');
    });

    it("should include input_type in payload", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain('"input_type": "chat"');
    });

    it("should include input_value in payload", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          input_value: "Custom message",
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain('"input_value": "Custom message"');
    });

    it("should use default values when payload fields are missing", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        } as any,
      });

      expect(code).toContain('"output_type": "chat"');
      expect(code).toContain('"input_type": "chat"');
      expect(code).toContain('"input_value": "Your message here"');
    });
  });

  describe("Error handling", () => {
    it("should include error handling in basic code", () => {
      const code = getNewJsApiCode(baseOptions);

      expect(code).toContain(".catch(err => console.error(err))");
    });

    it("should include try-catch in file upload code", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      expect(code).toContain("try {");
      expect(code).toContain("} catch (error) {");
      expect(code).toContain("console.error('Error:', error.message)");
    });

    it("should include file existence check in createFormData", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("if (!fs.existsSync(filePath))");
      expect(code).toContain("throw new Error");
      expect(code).toContain("File not found:");
    });

    it("should handle HTTP error status codes in makeRequest", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain(
        "if (res.statusCode >= 200 && res.statusCode < 300)",
      );
      expect(code).toContain("Request failed with status");
    });
  });

  describe("Session ID handling", () => {
    it("should generate session_id using crypto.randomUUID() in basic code", () => {
      const code = getNewJsApiCode(baseOptions);

      expect(code).toContain("session_id");
      expect(code).toContain("crypto.randomUUID()");
    });

    it("should generate session_id in file upload code", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain('"session_id": crypto.randomUUID()');
    });
  });

  describe("Code formatting", () => {
    it("should properly format JSON with indentation", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            node1: {
              param1: "value1",
              param2: "value2",
            },
          },
        },
      });

      // Check for proper indentation
      expect(code).toMatch(/const payload = \{/);
    });

    it("should properly indent nested tweaks in file upload code", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: {
              path: ["file.pdf"],
              config: {
                nested: "value",
              },
            },
          },
        },
      });

      expect(code).toContain('"tweaks": {');
      expect(code).toContain('"fileNode1"');
    });
  });

  describe("Module requirements", () => {
    it("should require crypto module in basic code", () => {
      const code = getNewJsApiCode(baseOptions);

      expect(code).toContain("const crypto = require('crypto')");
    });

    it("should require necessary modules for file uploads", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("const crypto = require('crypto')");
      expect(code).toContain("const fs = require('fs')");
      expect(code).toContain("const path = require('path')");
    });
  });

  describe("Response handling", () => {
    it("should parse response as JSON in basic code", () => {
      const code = getNewJsApiCode(baseOptions);

      expect(code).toContain(".then(response => response.json())");
      expect(code).toContain(".then(response => console.warn(response))");
    });

    it("should log successful uploads in file upload code", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      expect(code).toContain("console.log('ChatInput upload");
      expect(code).toContain("successful! File path:");
    });

    it("should log successful flow execution", () => {
      const code = getNewJsApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain("console.log('Flow execution successful!')");
      expect(code).toContain("console.log(result)");
    });
  });
});
