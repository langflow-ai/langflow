import { getNewPythonApiCode } from "../get-python-api-code";

// Mock the customGetHostProtocol
jest.mock("@/customization/utils/custom-get-host-protocol", () => ({
  customGetHostProtocol: () => ({
    protocol: "https:",
    host: "localhost:3000",
  }),
}));

describe("getNewPythonApiCode", () => {
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
    it("should generate valid Python code with API key authentication", () => {
      const code = getNewPythonApiCode(baseOptions);

      // Check imports
      expect(code).toContain("import requests");
      expect(code).toContain("import os");
      expect(code).toContain("import uuid");

      // Check API key setup
      expect(code).toContain("api_key = 'YOUR_API_KEY_HERE'");
      expect(code).toContain('headers = {"x-api-key": api_key}');

      // Check URL construction
      expect(code).toContain(
        'url = "https://localhost:3000/api/v1/run/test-endpoint"',
      );

      // Check session ID generation
      expect(code).toContain('payload["session_id"] = str(uuid.uuid4())');

      // Check request execution
      expect(code).toContain('requests.request("POST", url, json=payload');
      expect(code).toContain("response.raise_for_status()");

      // Check error handling
      expect(code).toContain("except requests.exceptions.RequestException");
      expect(code).toContain("except ValueError");
    });

    it("should generate valid Python code without API key authentication", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        shouldDisplayApiKey: false,
      });

      // Check imports
      expect(code).toContain("import requests");
      expect(code).toContain("import uuid");

      // Should NOT contain API key
      expect(code).not.toContain("api_key = 'YOUR_API_KEY_HERE'");
      expect(code).not.toContain('headers = {"x-api-key": api_key}');

      // Check session ID generation
      expect(code).toContain('payload["session_id"] = str(uuid.uuid4())');

      // Check request execution
      expect(code).toContain('requests.request("POST", url, json=payload');
    });

    it("should use flowId when endpointName is not provided", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        endpointName: "",
      });

      expect(code).toContain(
        'url = "https://localhost:3000/api/v1/run/test-flow-123"',
      );
    });

    it("should convert JavaScript booleans to Python booleans", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            node1: { enabled: true, disabled: false },
          },
        },
      });

      expect(code).toContain("True");
      expect(code).toContain("False");
      expect(code).not.toContain(": true");
      expect(code).not.toContain(": false");
    });

    it("should convert null to None", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            node1: { value: null },
          },
        },
      });

      expect(code).toContain("None");
      expect(code).not.toContain(": null");
    });
  });

  describe("File upload handling - ChatInput files (v1 API)", () => {
    it("should generate multi-step code for single ChatInput file", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      // Check for file upload step
      expect(code).toContain("# Step 1: Upload file for ChatInput chatNode1");
      expect(code).toContain('with open("your_image_1.jpg", "rb") as f:');
      expect(code).toContain('f"{base_url}/api/v1/files/upload/{flow_id}"');
      expect(code).toContain('files={"file": f}');
      expect(code).toContain('chat_file_path_1 = response.json()["file_path"]');

      // Check for flow execution step
      expect(code).toContain("# Step 2: Execute flow with all file paths");
      expect(code).toContain('"chatNode1"');

      // Check base URL and flow ID are defined
      expect(code).toContain('base_url = "https://localhost:3000"');
      expect(code).toContain('flow_id = "test-flow-123"');
    });

    it("should generate multi-step code for multiple ChatInput files", () => {
      const code = getNewPythonApiCode({
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
      expect(code).toContain("# Step 1: Upload file for ChatInput chatNode1");
      expect(code).toContain("# Step 2: Upload file for ChatInput chatNode2");
      expect(code).toContain('with open("your_image_1.jpg", "rb") as f:');
      expect(code).toContain('with open("your_image_2.jpg", "rb") as f:');
      expect(code).toContain("chat_file_path_1");
      expect(code).toContain("chat_file_path_2");

      // Check for flow execution step
      expect(code).toContain("# Step 3: Execute flow with all file paths");
    });
  });

  describe("File upload handling - File/VideoFile components (v2 API)", () => {
    it("should generate multi-step code for File component with path array", () => {
      const code = getNewPythonApiCode({
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
        "# Step 1: Upload file for File/VideoFile fileNode1",
      );
      expect(code).toContain('with open("your_file_1.pdf", "rb") as f:');
      expect(code).toContain('f"{base_url}/api/v2/files"');
      expect(code).toContain('file_path_1 = response.json()["path"]');

      // Check for flow execution step
      expect(code).toContain("# Step 2: Execute flow with all file paths");
      expect(code).toContain('"fileNode1"');
    });

    it("should generate multi-step code for VideoFile component with file_path string", () => {
      const code = getNewPythonApiCode({
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
        "# Step 1: Upload file for File/VideoFile videoNode1",
      );
      expect(code).toContain('with open("your_file_1.pdf", "rb") as f:');
      expect(code).toContain('f"{base_url}/api/v2/files"');
      expect(code).toContain('file_path_1 = response.json()["path"]');

      // Check for flow execution step
      expect(code).toContain("# Step 2: Execute flow with all file paths");
    });

    it("should generate multi-step code for multiple File/VideoFile components", () => {
      const code = getNewPythonApiCode({
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
        "# Step 1: Upload file for File/VideoFile fileNode1",
      );
      expect(code).toContain(
        "# Step 2: Upload file for File/VideoFile videoNode1",
      );
      expect(code).toContain("file_path_1");
      expect(code).toContain("file_path_2");

      // Check for flow execution step
      expect(code).toContain("# Step 3: Execute flow with all file paths");
    });
  });

  describe("Mixed file types handling", () => {
    it("should handle both ChatInput and File/VideoFile uploads", () => {
      const code = getNewPythonApiCode({
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
      expect(code).toContain("# Step 1: Upload file for ChatInput chatNode1");
      expect(code).toContain("/api/v1/files/upload/");

      // Check for File/VideoFile uploads (v2 API)
      expect(code).toContain(
        "# Step 2: Upload file for File/VideoFile fileNode1",
      );
      expect(code).toContain(
        "# Step 3: Upload file for File/VideoFile videoNode1",
      );
      expect(code).toContain("/api/v2/files");

      // Check for flow execution step
      expect(code).toContain("# Step 4: Execute flow with all file paths");
    });

    it("should handle file uploads mixed with non-file tweaks", () => {
      const code = getNewPythonApiCode({
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
      expect(code).toContain("# Step 1: Upload file for ChatInput chatNode1");

      // Check that non-file tweaks are included
      expect(code).toContain('"textNode1"');
      expect(code).toContain('"numberNode1"');
      expect(code).toContain('"some text"');
      expect(code).toContain("42");
    });
  });

  describe("Authentication handling", () => {
    it("should include API key in file upload requests when shouldDisplayApiKey is true", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        shouldDisplayApiKey: true,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      expect(code).toContain("api_key = 'YOUR_API_KEY_HERE'");
      expect(code).toContain('headers = {"x-api-key": api_key}');
      expect(code).toContain("headers=headers");
    });

    it("should not include API key when shouldDisplayApiKey is false", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        shouldDisplayApiKey: false,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      expect(code).not.toContain("api_key = 'YOUR_API_KEY_HERE'");
      expect(code).not.toContain('headers = {"x-api-key": api_key}');
    });
  });

  describe("Edge cases", () => {
    it("should handle empty tweaks object", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {},
        },
      });

      // Should generate basic code without file uploads
      expect(code).toContain("import requests");
      expect(code).toContain('payload["session_id"] = str(uuid.uuid4())');
      expect(code).not.toContain("# Step 1:");
    });

    it("should handle undefined tweaks", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          output_type: "chat",
          input_type: "chat",
          input_value: "Test",
        },
      });

      // Should generate basic code without file uploads
      expect(code).toContain("import requests");
      expect(code).not.toContain("# Step 1:");
    });

    it("should handle empty flowId", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        flowId: "",
        endpointName: "my-endpoint",
      });

      expect(code).toContain("/api/v1/run/my-endpoint");
    });

    it("should handle empty endpointName", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        endpointName: "",
      });

      expect(code).toContain("/api/v1/run/test-flow-123");
    });

    it("should handle special characters in input_value", () => {
      const code = getNewPythonApiCode({
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
      const code = getNewPythonApiCode({
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
      expect(code).toContain("nested");
      expect(code).toContain("123");
    });

    it("should handle array values in tweaks", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            arrayNode: {
              values: [1, 2, 3],
              names: ["a", "b", "c"],
            },
          },
        },
      });

      expect(code).toContain('"arrayNode"');
      // Arrays are formatted with newlines, check for individual elements
      expect(code).toContain("1");
      expect(code).toContain("2");
      expect(code).toContain("3");
    });
  });

  describe("Payload structure", () => {
    it("should include output_type in payload", () => {
      const code = getNewPythonApiCode({
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
      const code = getNewPythonApiCode({
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
      const code = getNewPythonApiCode({
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
      const code = getNewPythonApiCode({
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

  describe("Code formatting", () => {
    it("should properly format JSON with indentation", () => {
      const code = getNewPythonApiCode({
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

      // Check for proper indentation in payload
      expect(code).toMatch(/payload = \{[\s\S]*\}/);
    });

    it("should properly indent nested tweaks in file upload code", () => {
      const code = getNewPythonApiCode({
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

      // Check that tweaks are properly formatted
      expect(code).toContain('"tweaks": {');
      expect(code).toContain('"fileNode1"');
    });
  });

  describe("Error handling", () => {
    it("should include try-catch blocks in basic code", () => {
      const code = getNewPythonApiCode(baseOptions);

      expect(code).toContain("try:");
      expect(code).toContain(
        "except requests.exceptions.RequestException as e:",
      );
      expect(code).toContain('print(f"Error making API request: {e}")');
      expect(code).toContain("except ValueError as e:");
      expect(code).toContain('print(f"Error parsing response: {e}")');
    });

    it("should include raise_for_status() calls in file upload code", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      });

      expect(code).toContain("response.raise_for_status()");
    });
  });

  describe("Session ID handling", () => {
    it("should generate session_id using uuid.uuid4() in basic code", () => {
      const code = getNewPythonApiCode(baseOptions);

      expect(code).toContain('payload["session_id"] = str(uuid.uuid4())');
    });

    it("should generate session_id in file upload code", () => {
      const code = getNewPythonApiCode({
        ...baseOptions,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(code).toContain('"session_id": str(uuid.uuid4())');
    });
  });
});
