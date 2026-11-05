import { createFileUpload } from "@/helpers/create-file-upload";

const CHROME_MODERN =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36";
const CHROME_LEGACY =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36";
const FIREFOX_MODERN =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0";
const SAFARI_MODERN =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15";
const IOS_LEGACY =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1";
const originalUserAgent = navigator.userAgent;

const setUserAgent = (userAgent: string) => {
  Object.defineProperty(navigator, "userAgent", {
    value: userAgent,
    configurable: true,
  });
};

const getInput = () =>
  document.querySelector<HTMLInputElement>('[data-testid="hidden-file-input"]');

const selectFiles = (input: HTMLInputElement, files: File[]) => {
  Object.defineProperty(input, "files", { value: files, configurable: true });
  input.dispatchEvent(new Event("change"));
};

describe("createFileUpload", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    setUserAgent(CHROME_MODERN);
  });

  afterEach(() => {
    setUserAgent(originalUserAgent);
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

  it.each([
    ["Chrome", CHROME_MODERN],
    ["Firefox", FIREFOX_MODERN],
    ["Safari", SAFARI_MODERN],
  ])(
    "keeps the input attached when focus returns before the change event on %s",
    async (_browser, userAgent) => {
      setUserAgent(userAgent);
      const result = createFileUpload();
      const input = getInput() as HTMLInputElement;

      document.dispatchEvent(new Event("focus"));
      jest.advanceTimersByTime(5000);

      expect(input.isConnected).toBe(true);

      const file = new File(["x"], "a.json", { type: "application/json" });
      selectFiles(input, [file]);

      await expect(result).resolves.toEqual([file]);
    },
  );

  it.each([
    ["Chrome 109", CHROME_LEGACY],
    ["iOS Safari 15.6", IOS_LEGACY],
  ])(
    "resolves with no files and removes the input on focus without native cancel support on %s",
    async (_browser, userAgent) => {
      setUserAgent(userAgent);
      const result = createFileUpload();
      const input = getInput() as HTMLInputElement;

      document.dispatchEvent(new Event("focus"));
      jest.advanceTimersByTime(100);

      expect(input.isConnected).toBe(false);
      await expect(result).resolves.toEqual([]);
    },
  );

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
