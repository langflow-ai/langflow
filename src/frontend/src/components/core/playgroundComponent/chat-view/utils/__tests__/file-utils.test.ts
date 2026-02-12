import { getBaseUrl } from "@/customization/utils/urls";
import {
  extractFileInfo,
  formatFileName,
  getFileDisplayName,
  getFilePreviewUrl,
  isImageFile,
} from "../file-utils";

// Mock the getBaseUrl function
jest.mock("@/customization/utils/urls", () => ({
  getBaseUrl: jest.fn(() => "http://localhost:3000/api/v1/"),
}));

const mockGetBaseUrl = getBaseUrl as jest.MockedFunction<typeof getBaseUrl>;

beforeEach(() => {
  mockGetBaseUrl.mockReturnValue("http://localhost:3000/api/v1/");
});

describe("file-utils", () => {
  describe("isImageFile", () => {
    describe("File object detection", () => {
      it("should_return_true_for_browser_File_with_image_mime_type", () => {
        const file = new File(["content"], "test.jpg", {
          type: "image/jpeg",
        });
        expect(isImageFile(file)).toBe(true);
      });

      it("should_return_true_for_browser_File_with_image_prefix", () => {
        const file = new File(["content"], "test.png", {
          type: "image/png",
        });
        expect(isImageFile(file)).toBe(true);
      });

      it("should_return_false_for_browser_File_with_text_type", () => {
        const file = new File(["content"], "test.txt", {
          type: "text/plain",
        });
        expect(isImageFile(file)).toBe(false);
      });
    });

    describe("Windows path normalization", () => {
      it("should_detect_image_from_Windows_backslash_path", () => {
        const windowsPath = "C:\\Users\\test\\image.jpg";
        expect(isImageFile(windowsPath)).toBe(true);
      });

      it("should_detect_image_from_nested_Windows_path", () => {
        const windowsPath = "flow123\\subfolder\\image.png";
        expect(isImageFile(windowsPath)).toBe(true);
      });

      it("should_detect_image_from_mixed_path_separators", () => {
        const mixedPath = "flow123/subfolder\\image.gif";
        expect(isImageFile(mixedPath)).toBe(true);
      });

      it("should_reject_non_image_from_Windows_path", () => {
        const windowsPath = "C:\\Users\\test\\document.pdf";
        expect(isImageFile(windowsPath)).toBe(false);
      });
    });

    describe("Unix path handling", () => {
      it("should_detect_image_from_Unix_forward_slash_path", () => {
        const unixPath = "/home/user/image.jpg";
        expect(isImageFile(unixPath)).toBe(true);
      });

      it("should_detect_image_from_flow_path", () => {
        const flowPath = "flow123/image.webp";
        expect(isImageFile(flowPath)).toBe(true);
      });
    });

    describe("Object with path and type properties", () => {
      it("should_prioritize_path_extension_over_type_property", () => {
        const fileObj = {
          path: "flow123\\image.jpg",
          type: "text/plain", // Conflicting type
        };
        expect(isImageFile(fileObj)).toBe(true);
      });

      it("should_fall_back_to_type_property_when_path_extension_invalid", () => {
        const fileObj = {
          path: "flow123\\unknown",
          type: "image/png",
        };
        expect(isImageFile(fileObj)).toBe(true);
      });

      it("should_normalize_Windows_paths_in_object", () => {
        const fileObj = {
          path: "C:\\temp\\folder\\image.bmp",
          type: "application/octet-stream",
        };
        expect(isImageFile(fileObj)).toBe(true);
      });
    });

    describe("Edge cases", () => {
      it("should_handle_empty_string_path", () => {
        expect(isImageFile("")).toBe(false);
      });

      it("should_handle_path_without_extension", () => {
        expect(isImageFile("just-a-filename")).toBe(false);
      });

      it("should_handle_path_with_multiple_dots", () => {
        expect(isImageFile("file.backup.jpg")).toBe(true);
      });

      it("should_handle_uppercase_extension", () => {
        expect(isImageFile("image.JPG")).toBe(true);
        expect(isImageFile("C:\\Images\\photo.PNG")).toBe(true);
      });

      it("should_handle_null_or_undefined_input", () => {
        expect(isImageFile(null as any)).toBe(false);
        expect(isImageFile(undefined as any)).toBe(false);
      });
    });
  });

  describe("getFileDisplayName", () => {
    describe("File object handling", () => {
      it("should_return_file_name_from_browser_File", () => {
        const file = new File(["content"], "test-image.jpg");
        expect(getFileDisplayName(file)).toBe("test-image.jpg");
      });
    });

    describe("Windows path normalization", () => {
      it("should_extract_filename_from_Windows_absolute_path", () => {
        const windowsPath = "C:\\Users\\username\\Documents\\report.pdf";
        expect(getFileDisplayName(windowsPath)).toBe("report.pdf");
      });

      it("should_extract_filename_from_Windows_relative_path", () => {
        const windowsPath = "folder\\subfolder\\image.png";
        expect(getFileDisplayName(windowsPath)).toBe("image.png");
      });

      it("should_handle_mixed_path_separators", () => {
        const mixedPath = "flow/data\\files\\document.txt";
        expect(getFileDisplayName(mixedPath)).toBe("document.txt");
      });

      it("should_handle_single_backslash_path", () => {
        const path = "flow123\\image.jpg";
        expect(getFileDisplayName(path)).toBe("image.jpg");
      });
    });

    describe("Unix path handling", () => {
      it("should_extract_filename_from_Unix_path", () => {
        const unixPath = "/home/user/documents/file.txt";
        expect(getFileDisplayName(unixPath)).toBe("file.txt");
      });

      it("should_extract_filename_from_relative_Unix_path", () => {
        const unixPath = "folder/subfolder/image.png";
        expect(getFileDisplayName(unixPath)).toBe("image.png");
      });
    });

    describe("Object with name and path properties", () => {
      it("should_prefer_name_property_when_available", () => {
        const fileObj = {
          name: "custom-name.jpg",
          path: "C:\\long\\path\\different-name.jpg",
        };
        expect(getFileDisplayName(fileObj)).toBe("custom-name.jpg");
      });

      it("should_extract_from_path_when_no_name_property", () => {
        const fileObj = {
          path: "flow123\\folder\\image.png",
        };
        expect(getFileDisplayName(fileObj)).toBe("image.png");
      });
    });

    describe("Edge cases", () => {
      it("should_handle_empty_string", () => {
        expect(getFileDisplayName("")).toBe("");
      });

      it("should_return_original_string_when_no_separators", () => {
        expect(getFileDisplayName("filename")).toBe("filename");
      });

      it("should_handle_path_ending_with_separator", () => {
        // When path ends with \, it gets normalized to / and split creates empty string at end
        expect(getFileDisplayName("folder\\")).toBe("folder\\"); // Falls back to original
        expect(getFileDisplayName("folder/")).toBe("folder/"); // Falls back to original
      });
    });
  });

  describe("getFilePreviewUrl", () => {
    describe("File object handling", () => {
      it("should_return_object_URL_for_browser_File", () => {
        // Mock URL.createObjectURL
        const mockObjectURL = "blob:http://localhost/123-456";
        global.URL.createObjectURL = jest.fn(() => mockObjectURL);

        const file = new File(["content"], "test.jpg", {
          type: "image/jpeg",
        });

        expect(getFilePreviewUrl(file)).toBe(mockObjectURL);
        expect(URL.createObjectURL).toHaveBeenCalledWith(file);
      });

      it("should_return_null_for_non_image_File", () => {
        const file = new File(["content"], "test.txt", {
          type: "text/plain",
        });

        expect(getFilePreviewUrl(file)).toBeNull();
      });
    });

    describe("Windows path normalization and URL construction", () => {
      it("should_normalize_Windows_path_and_create_URL", () => {
        const windowsPath = "flow123\\subfolder\\image.jpg";
        const expected = "http://localhost:3000/api/v1/files/images/flow123/subfolder/image.jpg";

        expect(getFilePreviewUrl(windowsPath)).toBe(expected);
      });

      it("should_handle_absolute_Windows_path", () => {
        // Note: This tests the current behavior, but absolute paths shouldn't typically be used
        const windowsPath = "C:\\temp\\flow123\\image.png";
        const expected = "http://localhost:3000/api/v1/files/images/C%3A/temp/flow123/image.png";

        expect(getFilePreviewUrl(windowsPath)).toBe(expected);
      });

      it("should_encode_special_characters_in_path_segments", () => {
        const pathWithSpaces = "flow 123\\folder name\\image file.jpg";
        const expected = "http://localhost:3000/api/v1/files/images/flow%20123/folder%20name/image%20file.jpg";

        expect(getFilePreviewUrl(pathWithSpaces)).toBe(expected);
      });

      it("should_handle_mixed_path_separators", () => {
        const mixedPath = "flow123/data\\images\\photo.png";
        const expected = "http://localhost:3000/api/v1/files/images/flow123/data/images/photo.png";

        expect(getFilePreviewUrl(mixedPath)).toBe(expected);
      });
    });

    describe("Unix path handling", () => {
      it("should_create_URL_for_Unix_path", () => {
        const unixPath = "flow123/images/photo.jpg";
        const expected = "http://localhost:3000/api/v1/files/images/flow123/images/photo.jpg";

        expect(getFilePreviewUrl(unixPath)).toBe(expected);
      });
    });

    describe("Object with path property", () => {
      it("should_normalize_Windows_path_in_object", () => {
        const fileObj = {
          path: "flow123\\images\\photo.jpg",
          type: "image/jpeg",
        };
        const expected = "http://localhost:3000/api/v1/files/images/flow123/images/photo.jpg";

        expect(getFilePreviewUrl(fileObj)).toBe(expected);
      });

      it("should_return_null_for_non_image_object", () => {
        const fileObj = {
          path: "flow123\\documents\\file.txt",
          type: "text/plain",
        };

        expect(getFilePreviewUrl(fileObj)).toBeNull();
      });
    });

    describe("Edge cases", () => {
      it("should_return_null_for_empty_path_string", () => {
        expect(getFilePreviewUrl("")).toBeNull();
      });

      it("should_return_null_for_whitespace_only_path", () => {
        expect(getFilePreviewUrl("   ")).toBeNull();
      });

      it("should_handle_path_with_only_spaces", () => {
        expect(getFilePreviewUrl("   ")).toBeNull();
      });

      it("should_return_null_for_object_with_empty_path", () => {
        const fileObj = {
          path: "",
          type: "image/jpeg",
        };

        expect(getFilePreviewUrl(fileObj)).toBeNull();
      });
    });

    describe("Base URL variations", () => {
      it("should_work_with_different_base_URLs", () => {
        mockGetBaseUrl.mockReturnValue("https://example.com/api/");

        const path = "flow123\\image.jpg";
        const expected = "https://example.com/api/files/images/flow123/image.jpg";

        expect(getFilePreviewUrl(path)).toBe(expected);
      });

      it("should_handle_base_URL_without_trailing_slash", () => {
        mockGetBaseUrl.mockReturnValue("http://localhost:8000/api");

        const path = "flow123\\image.jpg";
        const expected = "http://localhost:8000/apifiles/images/flow123/image.jpg";

        expect(getFilePreviewUrl(path)).toBe(expected);
      });
    });
  });

  describe("formatFileName", () => {
    it("should_return_unchanged_when_under_limit", () => {
      const name = "short.jpg";
      expect(formatFileName(name)).toBe("short.jpg");
    });

    it("should_truncate_long_basename_with_ellipsis", () => {
      const name = "this-is-a-very-long-filename-that-should-be-truncated.jpg";
      const result = formatFileName(name, 25);

      expect(result).toContain("...");
      expect(result).toContain(".jpg");
      expect(result).toContain("this-is-a-very-long-filen");
    });

    it("should_preserve_short_basename_even_when_over_total_limit", () => {
      const name = "short.extension";
      expect(formatFileName(name, 10)).toBe("short.extension");
    });

    it("should_handle_files_without_extension", () => {
      const name = "filename-without-extension-very-long";
      const result = formatFileName(name, 25);

      // When no extension is found, lastIndexOf('.') returns -1, 
      // so baseName becomes entire string, fileExtension becomes the last part
      expect(result).toContain("...");
      expect(result.length).toBeGreaterThan(25);
    });

    it("should_use_custom_max_length", () => {
      const name = "moderately-long-filename.jpg";
      const result = formatFileName(name, 15);

      expect(result).toContain("...");
      expect(result).toContain(".jpg");
    });
  });

  describe("extractFileInfo", () => {
    describe("File object handling", () => {
      it("should_extract_info_from_browser_File", () => {
        const file = new File(["content"], "test.jpg", {
          type: "image/jpeg",
        });

        const result = extractFileInfo(file);

        expect(result).toEqual({
          name: "test.jpg",
          type: "image/jpeg",
          path: "test.jpg",
        });
      });
    });

    describe("Windows path normalization", () => {
      it("should_extract_info_from_Windows_path_string", () => {
        const windowsPath = "C:\\Users\\test\\image.jpg";

        const result = extractFileInfo(windowsPath);

        expect(result).toEqual({
          name: "image.jpg",
          type: "jpg",
          path: "C:\\Users\\test\\image.jpg",
        });
      });

      it("should_handle_relative_Windows_path", () => {
        const windowsPath = "flow123\\subfolder\\document.pdf";

        const result = extractFileInfo(windowsPath);

        expect(result).toEqual({
          name: "document.pdf",
          type: "pdf",
          path: "flow123\\subfolder\\document.pdf",
        });
      });
    });

    describe("Unix path handling", () => {
      it("should_extract_info_from_Unix_path", () => {
        const unixPath = "flow123/folder/image.png";

        const result = extractFileInfo(unixPath);

        expect(result).toEqual({
          name: "image.png",
          type: "png",
          path: "flow123/folder/image.png",
        });
      });
    });

    describe("Object with properties", () => {
      it("should_extract_info_from_file_object", () => {
        const fileObj = {
          path: "flow123\\image.jpg",
          type: "image/jpeg",
          name: "my-image.jpg",
        };

        const result = extractFileInfo(fileObj);

        expect(result).toEqual({
          name: "my-image.jpg",
          type: "image/jpeg",
          path: "flow123\\image.jpg",
        });
      });
    });

    describe("Edge cases", () => {
      it("should_handle_path_without_extension", () => {
        const result = extractFileInfo("just-filename");

        expect(result).toEqual({
          name: "just-filename",
          type: "just-filename", // split(".").pop() returns the whole string when no dots
          path: "just-filename",
        });
      });

      it("should_handle_empty_path", () => {
        const result = extractFileInfo("");

        expect(result).toEqual({
          name: "",
          type: "",
          path: "",
        });
      });

      it("should_handle_path_with_multiple_dots", () => {
        const result = extractFileInfo("file.backup.tar.gz");

        expect(result).toEqual({
          name: "file.backup.tar.gz",
          type: "gz",
          path: "file.backup.tar.gz",
        });
      });
    });
  });

  describe("Cross-platform compatibility tests", () => {
    describe("Mixed environment scenarios", () => {
      it("should_consistently_handle_paths_from_Windows_and_Unix", () => {
        const windowsPath = "flow123\\images\\photo.jpg";
        const unixPath = "flow123/images/photo.jpg";

        // Both should be treated as images
        expect(isImageFile(windowsPath)).toBe(true);
        expect(isImageFile(unixPath)).toBe(true);

        // Both should extract the same filename
        expect(getFileDisplayName(windowsPath)).toBe("photo.jpg");
        expect(getFileDisplayName(unixPath)).toBe("photo.jpg");

        // Both should generate equivalent URLs (normalized to forward slashes)
        const windowsUrl = getFilePreviewUrl(windowsPath);
        const unixUrl = getFilePreviewUrl(unixPath);
        expect(windowsUrl).toBe(unixUrl);
      });

      it("should_handle_complex_nested_paths_consistently", () => {
        const complexWindowsPath = "project\\data\\2024\\Q1\\reports\\image.png";
        const complexUnixPath = "project/data/2024/Q1/reports/image.png";

        expect(isImageFile(complexWindowsPath)).toBe(true);
        expect(isImageFile(complexUnixPath)).toBe(true);

        const windowsUrl = getFilePreviewUrl(complexWindowsPath);
        const unixUrl = getFilePreviewUrl(complexUnixPath);
        expect(windowsUrl).toBe(unixUrl);
      });
    });

    describe("CI environment compatibility", () => {
      it("should_work_in_Linux_CI_environment", () => {
        // Simulate Linux environment test
        const unixStylePath = "flow123/uploads/test-image.jpg";

        expect(isImageFile(unixStylePath)).toBe(true);
        expect(getFileDisplayName(unixStylePath)).toBe("test-image.jpg");
        expect(getFilePreviewUrl(unixStylePath)).toContain("flow123/uploads/test-image.jpg");
      });

      it("should_work_in_Windows_CI_environment", () => {
        // Simulate Windows environment test
        const windowsStylePath = "flow123\\uploads\\test-image.jpg";

        expect(isImageFile(windowsStylePath)).toBe(true);
        expect(getFileDisplayName(windowsStylePath)).toBe("test-image.jpg");
        expect(getFilePreviewUrl(windowsStylePath)).toContain("flow123/uploads/test-image.jpg");
      });
    });
  });
});