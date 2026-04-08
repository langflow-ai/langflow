import { act, renderHook, waitFor } from "@testing-library/react";
import type { AxiosError } from "axios";
import {
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "@/constants/file-upload-constants";
import { useChatFileUpload } from "@/shared/hooks/use-chat-file-upload";
import { useState } from "react";
import type { ChangeEvent } from "react";
import type { FilePreviewType } from "@/types/components";

const mutateMock = jest.fn();
const setErrorDataMock = jest.fn();
const validateFileSizeMock = jest.fn();
const isAllowedChatAttachmentFileMock = jest.fn();

jest.mock("@/controllers/API/queries/files/use-post-upload-file", () => ({
  usePostUploadFile: () => ({
    mutate: mutateMock,
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (state: { setErrorData: typeof setErrorDataMock }) => unknown,
  ) => selector({ setErrorData: setErrorDataMock }),
}));

jest.mock("@/shared/hooks/use-file-size-validator", () => ({
  __esModule: true,
  default: () => ({
    validateFileSize: validateFileSizeMock,
  }),
}));

jest.mock("@/utils/file-validation", () => ({
  isAllowedChatAttachmentFile: (file: File) =>
    isAllowedChatAttachmentFileMock(file),
}));

let enableFilesOnPlayground = true;

jest.mock("@/customization/feature-flags", () => ({
  get ENABLE_FILES_ON_PLAYGROUND() {
    return enableFilesOnPlayground;
  },
}));

function makeFileList(file: File): FileList {
  if (typeof DataTransfer !== "undefined") {
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    return dataTransfer.files;
  }

  const fallback = {
    0: file,
    length: 1,
    item: (index: number) => (index === 0 ? file : null),
  };
  return fallback as unknown as FileList;
}

describe("useChatFileUpload", () => {
  beforeEach(() => {
    mutateMock.mockReset();
    setErrorDataMock.mockReset();
    validateFileSizeMock.mockReset();
    isAllowedChatAttachmentFileMock.mockReset();

    isAllowedChatAttachmentFileMock.mockReturnValue(true);
    enableFilesOnPlayground = true;
  });

  it("happy path: uploads and updates files state", async () => {
    mutateMock.mockImplementation(
      (
        _variables: unknown,
        options: {
          onSuccess: (data: { file_path: string }) => void;
        },
      ) => {
        options.onSuccess({ file_path: "flow123/uploads/a.png" });
      },
    );

    const { result } = renderHook(() => {
      const [files, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFiles } = useChatFileUpload({
        currentFlowId: "flow123",
        setFiles,
      });
      return { files, handleFiles };
    });

    const file = new File(["content"], "a.png", { type: "image/png" });

    act(() => {
      result.current.handleFiles(makeFileList(file));
    });

    await waitFor(() => {
      expect(result.current.files).toHaveLength(1);
      const entry = result.current.files[0] as {
        file: File;
        loading: boolean;
        error: boolean;
        path?: string;
      };
      expect(entry.file.name).toBe("a.png");
      expect(entry.loading).toBe(false);
      expect(entry.error).toBe(false);
      expect(entry.path).toBe("flow123/uploads/a.png");
    });
  });

  it("error path: when mutate fails it marks file errored and shows alert", async () => {
    mutateMock.mockImplementation(
      (
        _variables: unknown,
        options: {
          onError: (error: AxiosError<{ detail?: string }>) => void;
        },
      ) => {
        const error = {
          response: { data: { detail: "upload failed" } },
        } as unknown as AxiosError<{ detail?: string }>;
        options.onError(error);
      },
    );

    const { result } = renderHook(() => {
      const [files, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFiles } = useChatFileUpload({
        currentFlowId: "flow123",
        setFiles,
      });
      return { files, handleFiles };
    });

    act(() => {
      result.current.handleFiles(makeFileList(new File(["x"], "a.png")));
    });

    await waitFor(() => {
      expect(result.current.files).toHaveLength(1);
      const entry = result.current.files[0] as {
        loading: boolean;
        error: boolean;
      };
      expect(entry.loading).toBe(false);
      expect(entry.error).toBe(true);
      expect(setErrorDataMock).toHaveBeenCalled();

      const [payload] = setErrorDataMock.mock.calls[0] as [
        { title?: string; list?: unknown },
      ];
      expect(payload).toEqual(
        expect.objectContaining({
          title: "Error uploading file",
          list: expect.any(Array),
        }),
      );
      expect(payload.list as unknown[]).not.toHaveLength(0);
    });
  });

  it("validation path: rejects disallowed file types before upload", () => {
    isAllowedChatAttachmentFileMock.mockReturnValue(false);

    const { result } = renderHook(() => {
      const [, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFiles } = useChatFileUpload({
        currentFlowId: "flow123",
        setFiles,
      });
      return { handleFiles };
    });

    act(() => {
      result.current.handleFiles(makeFileList(new File(["x"], "a.exe")));
    });

    expect(mutateMock).not.toHaveBeenCalled();
    expect(setErrorDataMock).toHaveBeenCalledWith({
      title: "Error uploading file",
      list: [FS_ERROR_TEXT, SN_ERROR_TEXT],
    });
  });

  it("size path: oversized file is rejected (validateFileSize throws)", () => {
    validateFileSizeMock.mockImplementation(() => {
      throw new Error("Too large");
    });

    const { result } = renderHook(() => {
      const [, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFiles } = useChatFileUpload({
        currentFlowId: "flow123",
        setFiles,
      });
      return { handleFiles };
    });

    act(() => {
      result.current.handleFiles(makeFileList(new File(["x"], "a.png")));
    });

    expect(mutateMock).not.toHaveBeenCalled();
    expect(setErrorDataMock).toHaveBeenCalledWith({ title: "Too large" });
  });

  it("clipboard path: handles paste events with files", async () => {
    mutateMock.mockImplementation(
      (
        _variables: unknown,
        options: {
          onSuccess: (data: { file_path: string }) => void;
        },
      ) => {
        options.onSuccess({ file_path: "flow123/uploads/paste.png" });
      },
    );

    const { result } = renderHook(() => {
      const [files, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFileChange } = useChatFileUpload({
        currentFlowId: "flow123",
        setFiles,
      });
      return { files, handleFileChange };
    });

    const pastedFile = new File(["x"], "paste.png", { type: "image/png" });

    const fakeClipboardEvent = {
      clipboardData: {
        items: [
          {
            getAsFile: () => pastedFile,
          },
        ],
      },
    } as unknown as ClipboardEvent;

    act(() => {
      result.current.handleFileChange(fakeClipboardEvent);
    });

    await waitFor(() => {
      expect(result.current.files).toHaveLength(1);
      const entry = result.current.files[0] as { path?: string };
      expect(entry.path).toBe("flow123/uploads/paste.png");
    });
  });

  it("empty currentFlowId: still calls mutate with an empty id", async () => {
    mutateMock.mockImplementation(
      (
        variables: { file: File; id: string },
        options: {
          onSuccess: (data: { file_path: string }) => void;
        },
      ) => {
        expect(variables.id).toBe("");
        options.onSuccess({ file_path: "uploads/empty-flow.png" });
      },
    );

    const { result } = renderHook(() => {
      const [files, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFiles } = useChatFileUpload({
        currentFlowId: "",
        setFiles,
      });
      return { files, handleFiles };
    });

    act(() => {
      result.current.handleFiles(makeFileList(new File(["x"], "a.png")));
    });

    await waitFor(() => {
      expect(result.current.files).toHaveLength(1);
    });
  });

  it("stale-state safety: multiple uploads append rather than overwrite", async () => {
    mutateMock.mockImplementation(
      (
        _variables: unknown,
        options: {
          onSuccess: (data: { file_path: string }) => void;
        },
      ) => {
        options.onSuccess({ file_path: "uploads/ok.png" });
      },
    );

    const { result } = renderHook(() => {
      const [files, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFiles } = useChatFileUpload({
        currentFlowId: "flow123",
        setFiles,
      });
      return { files, handleFiles };
    });

    act(() => {
      result.current.handleFiles(makeFileList(new File(["x"], "a.png")));
      result.current.handleFiles(makeFileList(new File(["y"], "b.png")));
    });

    await waitFor(() => {
      expect(result.current.files).toHaveLength(2);
    });
  });

  it("playground gating: when uploads disabled it clears input value and does nothing", () => {
    enableFilesOnPlayground = false;

    const { result } = renderHook(() => {
      const [, setFiles] = useState<FilePreviewType[]>([]);
      const { handleFileChange } = useChatFileUpload({
        currentFlowId: "flow123",
        setFiles,
        playgroundPage: true,
      });
      return { handleFileChange };
    });

    const input = document.createElement("input");
    input.value = "should-clear";

    const changeEvent = {
      target: input,
    } as unknown as ChangeEvent<HTMLInputElement>;

    act(() => {
      result.current.handleFileChange(changeEvent);
    });

    expect(input.value).toBe("");
    expect(mutateMock).not.toHaveBeenCalled();
    expect(setErrorDataMock).not.toHaveBeenCalled();
  });
});
