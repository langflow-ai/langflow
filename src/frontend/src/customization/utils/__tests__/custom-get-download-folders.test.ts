import { customGetDownloadFolderBlob } from "../custom-get-download-folders";

describe("customGetDownloadFolderBlob", () => {
  let createObjectURLMock: jest.Mock;
  let revokeObjectURLMock: jest.Mock;
  let linkClickMock: jest.Mock;
  let linkRemoveMock: jest.Mock;
  let setAttributeMock: jest.Mock;

  beforeEach(() => {
    createObjectURLMock = jest.fn(() => "blob:mock-url");
    revokeObjectURLMock = jest.fn();
    window.URL.createObjectURL = createObjectURLMock;
    window.URL.revokeObjectURL = revokeObjectURLMock;

    linkClickMock = jest.fn();
    linkRemoveMock = jest.fn();
    setAttributeMock = jest.fn();

    const originalCreateElement = document.createElement.bind(document);
    jest.spyOn(document, "createElement").mockImplementation((tag) => {
      const el = originalCreateElement(tag);
      if (tag === "a") {
        el.click = linkClickMock;
        el.remove = linkRemoveMock;
        el.setAttribute = setAttributeMock;
      }
      return el;
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("preserves CJK characters from the RFC 5987 filename* parameter instead of leaking it raw", () => {
    // Mirrors the header shape emitted by build_content_disposition() in
    // src/backend/base/langflow/api/utils/core.py for a project named "P龙".
    const response = {
      data: new Blob(["zip-bytes"]),
      headers: {
        "content-disposition":
          "attachment; filename=\"20260910_063512_P_flows.zip\"; filename*=UTF-8''20260910_063512_P%E9%BE%99_flows.zip",
      },
    };

    customGetDownloadFolderBlob(response, "folder-id", "P龙");

    expect(setAttributeMock).toHaveBeenCalledWith(
      "download",
      "20260910_063512_P龙_flows.zip",
    );
  });

  it("falls back to the folder name when no Content-Disposition header is present", () => {
    const response = {
      data: new Blob(["zip-bytes"]),
      headers: {},
    };

    customGetDownloadFolderBlob(response, "folder-id", "My Folder");

    expect(setAttributeMock).toHaveBeenCalledWith(
      "download",
      "My Folder.zip",
    );
  });
});
