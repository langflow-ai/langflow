import { createFileUpload } from "@/helpers/create-file-upload";

const getInput = () =>
  document.querySelector<HTMLInputElement>('[data-testid="hidden-file-input"]');

const selectFiles = (input: HTMLInputElement, files: File[]) => {
  Object.defineProperty(input, "files", { value: files, configurable: true });
  input.dispatchEvent(new Event("change"));
};

describe("createFileUpload", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    document.body.innerHTML = "";
  });

  it("opens the picker synchronously so the click keeps its user activation", () => {
    const click = jest
      .spyOn(HTMLInputElement.prototype, "click")
      .mockImplementation(() => {});

    createFileUpload();

    expect(click).toHaveBeenCalledTimes(1);
    click.mockRestore();
  });

  it("resolves with the selected files and removes the input", async () => {
    const result = createFileUpload({ multiple: true });
    const input = getInput() as HTMLInputElement;
    const file = new File(["x"], "a.txt", { type: "text/plain" });

    selectFiles(input, [file]);

    await expect(result).resolves.toEqual([file]);
    expect(getInput()).toBeNull();
  });

  it("keeps the input attached when focus returns before the change event", async () => {
    // Firefox moves focus back to the document before dispatching `change`.
    const result = createFileUpload();
    const input = getInput() as HTMLInputElement;

    document.dispatchEvent(new Event("focus"));
    jest.advanceTimersByTime(5000);

    expect(input.isConnected).toBe(true);

    const file = new File(["x"], "a.json", { type: "application/json" });
    selectFiles(input, [file]);

    await expect(result).resolves.toEqual([file]);
  });

  it("keeps the input attached while the picker stays open for a long time", async () => {
    const result = createFileUpload();
    const input = getInput() as HTMLInputElement;

    jest.advanceTimersByTime(5 * 60 * 1000);

    expect(input.isConnected).toBe(true);

    const file = new File(["x"], "a.json", { type: "application/json" });
    selectFiles(input, [file]);

    await expect(result).resolves.toEqual([file]);
  });

  it("resolves with no files and removes the input when the picker is cancelled", async () => {
    const result = createFileUpload();
    const input = getInput() as HTMLInputElement;

    input.dispatchEvent(new Event("cancel"));

    await expect(result).resolves.toEqual([]);
    expect(getInput()).toBeNull();
  });
});
