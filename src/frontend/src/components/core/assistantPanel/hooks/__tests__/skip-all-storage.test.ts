import { readSkipAll, writeSkipAll } from "../skip-all-storage";

const STORAGE_KEY = "langflow-assistant-skip-all";

describe("skip-all storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("readSkipAll", () => {
    it("should_return_false_when_key_is_absent", () => {
      expect(readSkipAll()).toBe(false);
    });

    it("should_return_true_when_key_is_the_string_true", () => {
      localStorage.setItem(STORAGE_KEY, "true");
      expect(readSkipAll()).toBe(true);
    });

    it("should_return_false_when_key_is_any_other_string", () => {
      // Defensive: anything other than the exact "true" string is treated
      // as off — we never want to enable a destructive behavior on the
      // back of a corrupted or partially-written localStorage value.
      localStorage.setItem(STORAGE_KEY, "yes");
      expect(readSkipAll()).toBe(false);
    });

    it("should_return_false_when_localStorage_throws", () => {
      // Private-browsing mode can throw on access. We must never crash.
      const original = Storage.prototype.getItem;
      Storage.prototype.getItem = () => {
        throw new Error("blocked");
      };
      try {
        expect(readSkipAll()).toBe(false);
      } finally {
        Storage.prototype.getItem = original;
      }
    });
  });

  describe("writeSkipAll", () => {
    it("should_set_key_to_string_true_when_value_is_true", () => {
      writeSkipAll(true);
      expect(localStorage.getItem(STORAGE_KEY)).toBe("true");
    });

    it("should_remove_key_when_value_is_false_to_keep_storage_tidy", () => {
      localStorage.setItem(STORAGE_KEY, "true");
      writeSkipAll(false);
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    });

    it("should_not_throw_when_localStorage_is_blocked", () => {
      const originalSet = Storage.prototype.setItem;
      Storage.prototype.setItem = () => {
        throw new Error("blocked");
      };
      try {
        expect(() => writeSkipAll(true)).not.toThrow();
      } finally {
        Storage.prototype.setItem = originalSet;
      }
    });
  });
});
