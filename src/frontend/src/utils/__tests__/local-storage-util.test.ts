import {
  getLocalStorage,
  removeLocalStorage,
  setLocalStorage,
} from "../local-storage-util";

describe("local-storage-util", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("reads, writes, and removes localStorage values", () => {
    setLocalStorage("languagePreference", "de");

    expect(getLocalStorage("languagePreference")).toBe("de");

    removeLocalStorage("languagePreference");

    expect(getLocalStorage("languagePreference")).toBeNull();
  });

  it("returns null when localStorage reads fail", () => {
    jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });

    expect(getLocalStorage("languagePreference")).toBeNull();
  });

  it("does not throw when localStorage writes fail", () => {
    jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });

    expect(() => setLocalStorage("languagePreference", "de")).not.toThrow();
  });

  it("does not throw when localStorage removals fail", () => {
    jest.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });

    expect(() => removeLocalStorage("languagePreference")).not.toThrow();
  });
});
