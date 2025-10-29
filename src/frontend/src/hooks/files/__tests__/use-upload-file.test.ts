import { renderHook, waitFor } from "@testing-library/react";
import { customPostUploadFileV2 } from "@/customization/hooks/use-custom-post-upload-file";
import { createFileUpload } from "@/helpers/create-file-upload";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import useUploadFile from "../use-upload-file";

// Mock dependencies
jest.mock("@/customization/hooks/use-custom-post-upload-file");
jest.mock("@/helpers/create-file-upload");
jest.mock("@/shared/hooks/use-file-size-validator");

describe("useUploadFile", () => {
  const mockUploadFileMutation = jest.fn();
  const mockValidateFileSize = jest.fn();
  const mockCreateFileUpload = createFileUpload as jest.MockedFunction<
    typeof createFileUpload
  >;

  beforeEach(() => {
    jest.clearAllMocks();
    mockValidateFileSize.mockReset();
    mockUploadFileMutation.mockReset();

    (customPostUploadFileV2 as jest.Mock).mockReturnValue({
      mutateAsync: mockUploadFileMutation,
    });

    (useFileSizeValidator as jest.Mock).mockReturnValue({
      validateFileSize: mockValidateFileSize,
    });

    mockUploadFileMutation.mockResolvedValue({ path: "file-id-123" });
  });

  describe("getFilesToUpload", () => {
    it("should return provided files when files argument is given", async () => {
      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      const mockFiles = [
        new File(["content"], "test.pdf", { type: "application/pdf" }),
      ];

      await waitFor(async () => {
        const uploadFile = result.current;
        mockUploadFileMutation.mockResolvedValue({ path: "file-id-123" });
        await uploadFile({ files: mockFiles });
      });

      expect(mockCreateFileUpload).not.toHaveBeenCalled();
    });

    it("should call createFileUpload when no files are provided", async () => {
      const mockFile = new File(["content"], "test.pdf", {
        type: "application/pdf",
      });
      mockCreateFileUpload.mockResolvedValue([mockFile]);

      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      await waitFor(async () => {
        const uploadFile = result.current;
        await uploadFile({ files: undefined });
      });

      expect(mockCreateFileUpload).toHaveBeenCalledWith({
        accept: ".pdf",
        multiple: false,
      });
    });

    it("should handle multiple file types in accept string", async () => {
      const mockFile = new File(["content"], "test.pdf", {
        type: "application/pdf",
      });
      mockCreateFileUpload.mockResolvedValue([mockFile]);

      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf", "txt", "csv"], multiple: true }),
      );

      await waitFor(async () => {
        const uploadFile = result.current;
        await uploadFile({ files: undefined });
      });

      expect(mockCreateFileUpload).toHaveBeenCalledWith({
        accept: ".pdf,.txt,.csv",
        multiple: true,
      });
    });
  });

  describe("uploadFile", () => {
    it("should successfully upload a valid file", async () => {
      const mockFile = new File(["content"], "test.pdf", {
        type: "application/pdf",
      });
      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      const uploadFile = result.current;
      const fileIds = await uploadFile({ files: [mockFile] });

      expect(mockValidateFileSize).toHaveBeenCalledWith(mockFile);
      expect(mockUploadFileMutation).toHaveBeenCalledWith({ file: mockFile });
      expect(fileIds).toEqual(["file-id-123"]);
    });

    it("should throw error when file extension is not allowed", async () => {
      const mockFile = new File(["content"], "test.exe", {
        type: "application/exe",
      });
      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf", "txt"], multiple: false }),
      );

      const uploadFile = result.current;

      await expect(uploadFile({ files: [mockFile] })).rejects.toThrow(
        "File type exe not allowed. Allowed types: pdf, txt",
      );

      expect(mockUploadFileMutation).not.toHaveBeenCalled();
    });

    it("should throw error when file has no extension", async () => {
      const mockFile = new File(["content"], "test", {
        type: "application/octet-stream",
      });
      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      const uploadFile = result.current;

      // When there's no dot, split(".").pop() returns the filename itself ("test")
      await expect(uploadFile({ files: [mockFile] })).rejects.toThrow(
        "File type test not allowed",
      );

      expect(mockUploadFileMutation).not.toHaveBeenCalled();
    });

    it("should throw error when multiple files provided but multiple is false", async () => {
      const mockFiles = [
        new File(["content1"], "test1.pdf", { type: "application/pdf" }),
        new File(["content2"], "test2.pdf", { type: "application/pdf" }),
      ];

      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      const uploadFile = result.current;

      await expect(uploadFile({ files: mockFiles })).rejects.toThrow(
        "Multiple files are not allowed",
      );
    });

    it("should upload multiple files when multiple is true", async () => {
      const mockFiles = [
        new File(["content1"], "test1.pdf", { type: "application/pdf" }),
        new File(["content2"], "test2.pdf", { type: "application/pdf" }),
      ];

      mockUploadFileMutation
        .mockResolvedValueOnce({ path: "file-id-1" })
        .mockResolvedValueOnce({ path: "file-id-2" });

      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: true }),
      );

      const uploadFile = result.current;
      const fileIds = await uploadFile({ files: mockFiles });

      expect(mockValidateFileSize).toHaveBeenCalledTimes(2);
      expect(mockUploadFileMutation).toHaveBeenCalledTimes(2);
      expect(fileIds).toEqual(["file-id-1", "file-id-2"]);
    });

    it("should validate file size before upload", async () => {
      mockValidateFileSize.mockImplementation(() => {
        throw new Error("File too large");
      });

      const mockFile = new File(["content"], "test.pdf", {
        type: "application/pdf",
      });
      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      const uploadFile = result.current;

      await expect(uploadFile({ files: [mockFile] })).rejects.toThrow(
        "File too large",
      );

      expect(mockUploadFileMutation).not.toHaveBeenCalled();
    });

    it("should handle upload mutation errors", async () => {
      // Reset mockValidateFileSize from previous test
      mockValidateFileSize.mockReset();
      mockUploadFileMutation.mockRejectedValue(new Error("Upload failed"));

      const mockFile = new File(["content"], "test.pdf", {
        type: "application/pdf",
      });
      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      const uploadFile = result.current;

      await expect(uploadFile({ files: [mockFile] })).rejects.toThrow(
        "Upload failed",
      );
    });

    it("should allow any file type when types is undefined", async () => {
      // Reset mocks to ensure clean state
      mockValidateFileSize.mockReset();
      mockUploadFileMutation
        .mockReset()
        .mockResolvedValue({ path: "file-id-123" });

      const mockFile = new File(["content"], "test.pdf", {
        type: "application/pdf",
      });
      const { result } = renderHook(() =>
        useUploadFile({ types: undefined, multiple: false }),
      );

      const uploadFile = result.current;
      const fileIds = await uploadFile({ files: [mockFile] });

      expect(mockUploadFileMutation).toHaveBeenCalledWith({ file: mockFile });
      expect(fileIds).toEqual(["file-id-123"]);
    });

    it("should handle case-insensitive file extensions", async () => {
      // Reset mocks to ensure clean state
      mockValidateFileSize.mockReset();
      mockUploadFileMutation
        .mockReset()
        .mockResolvedValue({ path: "file-id-123" });

      const mockFile = new File(["content"], "test.PDF", {
        type: "application/pdf",
      });
      const { result } = renderHook(() =>
        useUploadFile({ types: ["pdf"], multiple: false }),
      );

      const uploadFile = result.current;
      const fileIds = await uploadFile({ files: [mockFile] });

      expect(mockUploadFileMutation).toHaveBeenCalledWith({ file: mockFile });
      expect(fileIds).toEqual(["file-id-123"]);
    });
  });
});
