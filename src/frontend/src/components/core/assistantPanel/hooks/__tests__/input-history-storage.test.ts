import { pushHistory, readHistory } from "../input-history-storage";

const STORAGE_KEY = "langflow-assistant-input-history";
const MAX_HISTORY = 10;

describe("input-history storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("readHistory", () => {
    it("should_return_empty_array_when_key_is_absent", () => {
      expect(readHistory()).toEqual([]);
    });

    it("should_return_saved_array_when_key_holds_valid_json_array_of_strings", () => {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(["latest", "older", "oldest"]),
      );
      expect(readHistory()).toEqual(["latest", "older", "oldest"]);
    });

    it("should_return_empty_array_when_json_is_malformed", () => {
      localStorage.setItem(STORAGE_KEY, "not-json");
      expect(readHistory()).toEqual([]);
    });

    it("should_return_empty_array_when_payload_is_not_an_array_of_strings", () => {
      // Defensive: ignore anything that isn't a string[]. Don't crash, and
      // don't surface "12" / null as a recalled command.
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ value: "x" }));
      expect(readHistory()).toEqual([]);

      localStorage.setItem(STORAGE_KEY, JSON.stringify([1, 2, 3]));
      expect(readHistory()).toEqual([]);
    });

    it("should_return_empty_array_when_localStorage_getItem_throws", () => {
      const original = Storage.prototype.getItem;
      Storage.prototype.getItem = () => {
        throw new Error("blocked");
      };
      try {
        expect(readHistory()).toEqual([]);
      } finally {
        Storage.prototype.getItem = original;
      }
    });
  });

  describe("pushHistory", () => {
    it("should_prepend_new_value_at_index_zero_so_recall_up_returns_latest_first", () => {
      pushHistory("first");
      pushHistory("second");
      expect(readHistory()).toEqual(["second", "first"]);
    });

    it("should_cap_history_at_10_entries_dropping_oldest", () => {
      for (let i = 1; i <= MAX_HISTORY + 3; i += 1) {
        pushHistory(`entry-${i}`);
      }
      const stored = readHistory();
      expect(stored).toHaveLength(MAX_HISTORY);
      // newest-first → entry-13 at index 0, entry-4 at the end.
      expect(stored[0]).toBe(`entry-${MAX_HISTORY + 3}`);
      expect(stored[stored.length - 1]).toBe("entry-4");
    });

    it("should_dedup_consecutive_duplicates_so_pressing_up_doesnt_replay_the_same_command", () => {
      pushHistory("hello");
      pushHistory("hello");
      pushHistory("hello");
      expect(readHistory()).toEqual(["hello"]);
    });

    it("should_allow_a_repeat_value_when_a_different_command_separates_them", () => {
      // "build me a flow" / "tweak it" / "build me a flow" is legitimate.
      pushHistory("build me a flow");
      pushHistory("tweak it");
      pushHistory("build me a flow");
      expect(readHistory()).toEqual([
        "build me a flow",
        "tweak it",
        "build me a flow",
      ]);
    });

    it("should_ignore_empty_and_whitespace_only_values", () => {
      pushHistory("");
      pushHistory("   ");
      pushHistory("\n\t");
      expect(readHistory()).toEqual([]);
    });

    it("should_not_throw_when_localStorage_setItem_throws", () => {
      const original = Storage.prototype.setItem;
      Storage.prototype.setItem = () => {
        throw new Error("blocked");
      };
      try {
        expect(() => pushHistory("anything")).not.toThrow();
      } finally {
        Storage.prototype.setItem = original;
      }
    });
  });
});
