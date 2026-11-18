import { createFileUpload } from "@/helpers/create-file-upload";

const makeFile = () => new File(["x"], "a.txt", { type: "text/plain" });

const getInput = () =>
  document.querySelector<HTMLInputElement>('input[type="file"]');

describe("createFileUpload", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    document.body.innerHTML = "";
  });

  it("keeps a selection whose change event arrives after focus returns", async () => {
    const result = createFileUpload({ multiple: true });
    const input = getInput();
    expect(input).not.toBeNull();

    // Firefox order: the picker closes, focus returns to the document, and
    // only afterwards does the input dispatch `change`.
    document.dispatchEvent(new Event("focus"));
    jest.advanceTimersByTime(250);

    const file = makeFile();
    Object.defineProperty(input as HTMLInputElement, "files", {
      value: [file],
      configurable: true,
    });
    input?.dispatchEvent(new Event("change"));

    await expect(result).resolves.toEqual([file]);
  });

  it("resolves with no files when the picker is cancelled", async () => {
    const result = createFileUpload();

    document.dispatchEvent(new Event("focus"));
    jest.advanceTimersByTime(1000);

    await expect(result).resolves.toEqual([]);
  });

  it("keeps a selection that arrives before the focus grace period", async () => {
    const result = createFileUpload();
    const input = getInput();
    const file = makeFile();
    Object.defineProperty(input as HTMLInputElement, "files", {
      value: [file],
      configurable: true,
    });
    input?.dispatchEvent(new Event("change"));

    await expect(result).resolves.toEqual([file]);
  });
});
