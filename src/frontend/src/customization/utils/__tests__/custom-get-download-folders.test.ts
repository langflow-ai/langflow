import type { AxiosResponse } from "axios";
import { customGetDownloadFolderBlob } from "../custom-get-download-folders";

jest.mock("../analytics", () => ({ track: jest.fn() }));

// Header exactly as build_content_disposition emits it for a GB18030 project name
const GB18030_NAME = "20260910_063512_P〣凉嗀龵龬𤫉𫇭𫞩𬸦𠵍⿕_flows.zip";
const GB18030_HEADER = `attachment; filename="20260910_063512_P???????????_flows.zip"; filename*=UTF-8''${encodeURIComponent(GB18030_NAME)}`;

const buildResponse = (headers: Record<string, string>) =>
  ({ data: new Blob(["zip"]), headers }) as AxiosResponse<Blob>;

describe("customGetDownloadFolderBlob", () => {
  let downloaded: string | null;

  beforeEach(() => {
    downloaded = null;
    window.URL.createObjectURL = jest.fn(() => "blob:mock");
    window.URL.revokeObjectURL = jest.fn();
    jest
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        downloaded = this.getAttribute("download");
      });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("preserves GB18030 characters from the RFC 5987 filename* param", () => {
    customGetDownloadFolderBlob(
      buildResponse({ "content-disposition": GB18030_HEADER }),
      "folder-1",
      "P〣凉嗀龵龬𤫉𫇭𫞩𬸦𠵍⿕",
    );

    expect(downloaded).toBe(GB18030_NAME);
  });

  it("falls back to the folder name when there is no Content-Disposition header", () => {
    customGetDownloadFolderBlob(buildResponse({}), "folder-1", "My Project");

    expect(downloaded).toBe("My Project.zip");
  });
});
