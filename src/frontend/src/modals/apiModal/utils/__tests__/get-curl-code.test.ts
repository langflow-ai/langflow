import { getCurlWebhookCode, getNewCurlCode } from "../get-curl-code";

// Mock the customGetHostProtocol
jest.mock("@/customization/utils/custom-get-host-protocol", () => ({
  customGetHostProtocol: () => ({
    protocol: "https:",
    host: "localhost:3000",
  }),
}));

// Mock the feature flag
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
}));

describe("getCurlWebhookCode", () => {
  const baseOptions = {
    flowId: "test-flow-123",
    flowName: "Test Flow",
    endpointName: "test-endpoint",
    webhookAuthEnable: false,
  };

  describe("Basic webhook code generation", () => {
    it("should generate multiline webhook cURL code without authentication", () => {
      const code = getCurlWebhookCode({
        ...baseOptions,
        format: "multiline",
      });

      expect(code).toContain("curl -X POST");
      expect(code).toContain(
        "https://localhost:3000/api/v1/webhook/test-endpoint",
      );
      expect(code).toContain("'Content-Type: application/json'");
      expect(code).toContain('\'{"any": "data"}\'');
      expect(code).not.toContain("x-api-key");
    });

    it("should generate multiline webhook cURL code with authentication", () => {
      const code = getCurlWebhookCode({
        ...baseOptions,
        webhookAuthEnable: true,
        format: "multiline",
      });

      expect(code).toContain("curl -X POST");
      expect(code).toContain(
        "https://localhost:3000/api/v1/webhook/test-endpoint",
      );
      expect(code).toContain("'Content-Type: application/json'");
      expect(code).toContain("'x-api-key: <your api key>'");
      expect(code).toContain('\'{"any": "data"}\'');
    });

    it("should generate single-line webhook cURL code without authentication", () => {
      const code = getCurlWebhookCode({
        ...baseOptions,
        format: "singleline",
      });

      expect(code).toContain("curl -X POST");
      expect(code).toContain(
        '"https://localhost:3000/api/v1/webhook/test-endpoint"',
      );
      expect(code).toContain("'Content-Type: application/json'");
      expect(code).toContain('\'{"any": "data"}\'');
      expect(code).not.toContain("\n");
      expect(code).not.toContain("x-api-key");
    });

    it("should generate single-line webhook cURL code with authentication", () => {
      const code = getCurlWebhookCode({
        ...baseOptions,
        webhookAuthEnable: true,
        format: "singleline",
      });

      expect(code).toContain("curl -X POST");
      expect(code).toContain(
        '"https://localhost:3000/api/v1/webhook/test-endpoint"',
      );
      expect(code).toContain("'Content-Type: application/json'");
      expect(code).toContain("-H 'x-api-key: <your api key>'");
      expect(code).toContain('\'{"any": "data"}\'');
    });

    it("should use flowId when endpointName is not provided", () => {
      const code = getCurlWebhookCode({
        ...baseOptions,
        endpointName: "",
        format: "multiline",
      });

      expect(code).toContain(
        "https://localhost:3000/api/v1/webhook/test-flow-123",
      );
    });

    it("should default to multiline format when format is not specified", () => {
      const code = getCurlWebhookCode({
        flowId: "test",
        flowName: "Test",
        endpointName: "test",
        webhookAuthEnable: false,
      });

      // Multiline format has backslashes for line continuation
      expect(code).toContain("\\");
    });
  });

  describe("Edge cases for webhook code", () => {
    it("should handle empty flowId", () => {
      const code = getCurlWebhookCode({
        flowId: "",
        flowName: "Test",
        endpointName: "my-endpoint",
        webhookAuthEnable: false,
        format: "multiline",
      });

      expect(code).toContain("/api/v1/webhook/my-endpoint");
    });

    it("should handle special characters in endpoint name", () => {
      const code = getCurlWebhookCode({
        ...baseOptions,
        endpointName: "test-endpoint_v2.0",
        format: "multiline" as const,
      });

      expect(code).toContain("/api/v1/webhook/test-endpoint_v2.0");
    });
  });
});

describe("getNewCurlCode", () => {
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

  describe("Basic code generation without files - Unix", () => {
    it("should generate Unix cURL code with API key authentication", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
      }) as string;

      expect(code).toContain("curl --request POST");
      expect(code).toContain(
        "--url 'https://localhost:3000/api/v1/run/test-endpoint?stream=false'",
      );
      expect(code).toContain("--header 'Content-Type: application/json'");
      expect(code).toContain('--header "x-api-key: YOUR_API_KEY_HERE"');
      expect(code).toContain("YOUR_SESSION_ID_HERE");
      expect(code).toContain("\\"); // Line continuation
    });

    it("should generate Unix cURL code without API key authentication", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        shouldDisplayApiKey: false,
      }) as string;

      expect(code).toContain("curl --request POST");
      expect(code).toContain(
        "--url 'https://localhost:3000/api/v1/run/test-endpoint?stream=false'",
      );
      expect(code).toContain("--header 'Content-Type: application/json'");
      expect(code).not.toContain("x-api-key: YOUR_API_KEY_HERE");
      expect(code).toContain("YOUR_SESSION_ID_HERE");
    });

    it("should use flowId when endpointName is not provided", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        endpointName: "",
        platform: "unix",
      }) as string;

      expect(code).toContain("/api/v1/run/test-flow-123");
    });
  });

  describe("Basic code generation without files - PowerShell", () => {
    it("should generate PowerShell cURL code with API key authentication", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "powershell",
      }) as string;

      expect(code).toContain("$jsonData = @'");
      expect(code).toContain("'@");
      expect(code).toContain("curl.exe --request POST");
      expect(code).toContain(
        '--url "https://localhost:3000/api/v1/run/test-endpoint?stream=false"',
      );
      expect(code).toContain('--header "Content-Type: application/json"');
      expect(code).toContain('--header "x-api-key: YOUR_API_KEY_HERE"');
      expect(code).toContain("`"); // PowerShell line continuation
      expect(code).toContain("--data $jsonData");
    });

    it("should generate PowerShell cURL code without API key authentication", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "powershell",
        shouldDisplayApiKey: false,
      }) as string;

      expect(code).toContain("$jsonData = @'");
      expect(code).toContain("curl.exe --request POST");
      expect(code).not.toContain("x-api-key: YOUR_API_KEY_HERE");
      expect(code).toContain("--data $jsonData");
    });
  });

  describe("Platform auto-detection", () => {
    it("should auto-detect platform when not specified", () => {
      const code = getNewCurlCode(baseOptions) as string;

      // Should generate code (either Unix or PowerShell format)
      expect(code).toContain("curl");
      expect(code).toContain("/api/v1/run/test-endpoint");
    });
  });

  describe("File upload handling - ChatInput files (v1 API) - Unix", () => {
    it("should generate multi-step code for single ChatInput file", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result).toHaveProperty("steps");
      expect(Array.isArray(result.steps)).toBe(true);
      expect(result.steps).toHaveLength(2);

      // Check upload step
      expect(result.steps[0].title).toContain("Upload files");
      expect(result.steps[0].code).toContain("curl --request POST");
      expect(result.steps[0].code).toContain(
        "/api/v1/files/upload/test-flow-123",
      );
      expect(result.steps[0].code).toContain('--form "file=@your_image_1.jpg"');

      // Check execute step
      expect(result.steps[1].title).toContain("Execute");
      expect(result.steps[1].code).toContain("/api/v1/run/test-endpoint");
      expect(result.steps[1].code).toContain(
        "REPLACE_WITH_FILE_PATH_FROM_UPLOAD_1",
      );
    });

    it("should generate multi-step code for multiple ChatInput files", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image1.jpg" },
            chatNode2: { files: "image2.png" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check both upload commands in step 1
      expect(result.steps[0].code).toContain("your_image_1.jpg");
      expect(result.steps[0].code).toContain("your_image_2.jpg");

      // Check both file path placeholders in step 2
      expect(result.steps[1].code).toContain(
        "REPLACE_WITH_FILE_PATH_FROM_UPLOAD_1",
      );
      expect(result.steps[1].code).toContain(
        "REPLACE_WITH_FILE_PATH_FROM_UPLOAD_2",
      );
    });
  });

  describe("File upload handling - File/VideoFile components (v2 API) - Unix", () => {
    it("should generate multi-step code for File component with path array", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["document.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check upload step
      expect(result.steps[0].code).toContain("/api/v2/files");
      expect(result.steps[0].code).toContain('--form "file=@your_file_1.pdf"');

      // Check execute step
      expect(result.steps[1].code).toContain(
        "REPLACE_WITH_FILE_PATH_FROM_UPLOAD_1",
      );
    });

    it("should generate multi-step code for VideoFile component with file_path string", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            videoNode1: { file_path: "video.mp4" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check upload step
      expect(result.steps[0].code).toContain("/api/v2/files");
      expect(result.steps[0].code).toContain('--form "file=@your_file_1.pdf"');
    });

    it("should generate multi-step code for multiple File/VideoFile components", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["doc.pdf"] },
            videoNode1: { file_path: "vid.mp4" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check both uploads
      expect(result.steps[0].code).toContain("your_file_1.pdf");
      expect(result.steps[0].code).toContain("your_file_2.pdf");
      expect(result.steps[0].code).toContain("/api/v2/files");
    });
  });

  describe("File upload handling - PowerShell", () => {
    it("should generate multi-step PowerShell code for ChatInput file", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "powershell",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check upload step uses curl.exe
      expect(result.steps[0].code).toContain("curl.exe --request POST");
      expect(result.steps[0].code).toContain(
        "/api/v1/files/upload/test-flow-123",
      );
      expect(result.steps[0].code).toContain("`"); // PowerShell line continuation

      // Check execute step
      expect(result.steps[1].code).toContain("curl.exe -X POST");
      expect(result.steps[1].code).toContain("/api/v1/run/test-endpoint");
    });

    it("should generate multi-step PowerShell code for File component", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "powershell",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["document.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check upload step
      expect(result.steps[0].code).toContain("curl.exe --request POST");
      expect(result.steps[0].code).toContain("/api/v2/files");
    });
  });

  describe("Mixed file types handling", () => {
    it("should handle both ChatInput and File/VideoFile uploads", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
            fileNode1: { path: ["doc.pdf"] },
            videoNode1: { file_path: "video.mp4" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check for both v1 and v2 API uploads
      expect(result.steps[0].code).toContain("/api/v1/files/upload/");
      expect(result.steps[0].code).toContain("/api/v2/files");

      // Check all upload counter placeholders
      expect(result.steps[1].code).toContain(
        "REPLACE_WITH_FILE_PATH_FROM_UPLOAD_1",
      );
      expect(result.steps[1].code).toContain(
        "REPLACE_WITH_FILE_PATH_FROM_UPLOAD_2",
      );
      expect(result.steps[1].code).toContain(
        "REPLACE_WITH_FILE_PATH_FROM_UPLOAD_3",
      );
    });

    it("should handle file uploads mixed with non-file tweaks", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
            textNode1: { value: "some text" },
            numberNode1: { count: 42 },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps).toHaveLength(2);

      // Check that non-file tweaks are included in execute step
      expect(result.steps[1].code).toContain('"textNode1"');
      expect(result.steps[1].code).toContain('"numberNode1"');
    });
  });

  describe("Authentication handling in file uploads", () => {
    it("should include API key in file upload requests when shouldDisplayApiKey is true - Unix", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        shouldDisplayApiKey: true,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[0].code).toContain("x-api-key: YOUR_API_KEY_HERE");
      expect(result.steps[1].code).toContain("x-api-key: YOUR_API_KEY_HERE");
    });

    it("should not include API key when shouldDisplayApiKey is false - Unix", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        shouldDisplayApiKey: false,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[0].code).not.toContain(
        "x-api-key: YOUR_API_KEY_HERE",
      );
      expect(result.steps[1].code).not.toContain(
        "x-api-key: YOUR_API_KEY_HERE",
      );
    });

    it("should include API key in file upload requests when shouldDisplayApiKey is true - PowerShell", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "powershell",
        shouldDisplayApiKey: true,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[0].code).toContain("x-api-key: YOUR_API_KEY_HERE");
      expect(result.steps[1].code).toContain("x-api-key: YOUR_API_KEY_HERE");
    });

    it("should not include API key when shouldDisplayApiKey is false - PowerShell", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "powershell",
        shouldDisplayApiKey: false,
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            chatNode1: { files: "image.jpg" },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[0].code).not.toContain(
        "x-api-key: YOUR_API_KEY_HERE",
      );
      expect(result.steps[1].code).not.toContain(
        "x-api-key: YOUR_API_KEY_HERE",
      );
    });
  });

  describe("Edge cases", () => {
    it("should handle empty tweaks object", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {},
        },
      });

      // Should return string, not steps object
      expect(typeof code).toBe("string");
      expect(code).toContain("curl --request POST");
    });

    it("should handle undefined tweaks", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          output_type: "chat",
          input_type: "chat",
          input_value: "Test",
        },
      });

      // Should return string, not steps object
      expect(typeof code).toBe("string");
    });

    it("should handle empty flowId", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        flowId: "",
        endpointName: "my-endpoint",
        platform: "unix",
      }) as string;

      expect(code).toContain("/api/v1/run/my-endpoint");
    });

    it("should handle empty endpointName", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        endpointName: "",
        platform: "unix",
      }) as string;

      expect(code).toContain("/api/v1/run/test-flow-123");
    });

    it("should handle special characters in input_value", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          input_value: "Hello \"world\" with 'quotes'",
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain("Hello \"world\" with 'quotes'");
    });

    it("should handle deeply nested objects in tweaks", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
            complexNode: {
              config: {
                nested: {
                  value: 123,
                },
              },
            },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain('"complexNode"');
    });
  });

  describe("Payload structure in file uploads", () => {
    it("should include output_type in payload", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain('"output_type": "chat"');
    });

    it("should include input_type in payload", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain('"input_type": "chat"');
    });

    it("should include input_value in payload", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          input_value: "Custom message",
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain('"input_value": "Custom message"');
    });

    it("should use default values when payload fields are missing", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        } as any,
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain('"output_type": "chat"');
      expect(result.steps[1].code).toContain('"input_type": "chat"');
      expect(result.steps[1].code).toContain(
        '"input_value": "Your message here"',
      );
    });
  });

  describe("Session ID handling", () => {
    it("should include session_id placeholder in basic code", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
      }) as string;

      expect(code).toContain("YOUR_SESSION_ID_HERE");
    });

    it("should include session_id in file upload code", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain(
        '"session_id": "YOUR_SESSION_ID_HERE"',
      );
    });
  });

  describe("Code formatting", () => {
    it("should use backslashes for line continuation in Unix format", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
      }) as string;

      expect(code).toContain("\\");
    });

    it("should use backticks for line continuation in PowerShell format", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "powershell",
      }) as string;

      expect(code).toContain("`");
    });

    it("should properly format JSON in Unix multi-step code", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[1].code).toContain('"tweaks": {');
    });
  });

  describe("Return type consistency", () => {
    it("should return string when no files are present", () => {
      const code = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
      });

      expect(typeof code).toBe("string");
    });

    it("should return steps object when files are present", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      });

      expect(typeof result).toBe("object");
      expect(result).toHaveProperty("steps");
      expect(Array.isArray((result as any).steps)).toBe(true);
    });
  });

  describe("Step structure in file uploads", () => {
    it("should have correct structure for steps", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      result.steps.forEach((step) => {
        expect(step).toHaveProperty("title");
        expect(step).toHaveProperty("code");
        expect(typeof step.title).toBe("string");
        expect(typeof step.code).toBe("string");
      });
    });

    it("should have descriptive titles for steps", () => {
      const result = getNewCurlCode({
        ...baseOptions,
        platform: "unix",
        processedPayload: {
          ...baseOptions.processedPayload,
          tweaks: {
            fileNode1: { path: ["file.pdf"] },
          },
        },
      }) as { steps: { title: string; code: string }[] };

      expect(result.steps[0].title).toMatch(/upload/i);
      expect(result.steps[1].title).toMatch(/execute/i);
    });
  });
});
