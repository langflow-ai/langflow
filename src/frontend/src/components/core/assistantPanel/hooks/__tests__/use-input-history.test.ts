import { act, renderHook } from "@testing-library/react";

import { useInputHistory } from "../use-input-history";

const STORAGE_KEY = "langflow-assistant-input-history";

function seedHistory(entries: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

describe("useInputHistory", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("recall — empty history", () => {
    it("should_return_null_when_recall_up_with_no_history", () => {
      const { result } = renderHook(() => useInputHistory());
      let recalled: string | null = "sentinel";
      act(() => {
        recalled = result.current.recall("up", "current draft");
      });
      expect(recalled).toBeNull();
    });

    it("should_return_null_when_recall_down_with_no_history", () => {
      const { result } = renderHook(() => useInputHistory());
      let recalled: string | null = "sentinel";
      act(() => {
        recalled = result.current.recall("down", "current draft");
      });
      expect(recalled).toBeNull();
    });
  });

  describe("recall — Up walks back in time", () => {
    it("should_return_latest_entry_on_first_recall_up", () => {
      seedHistory(["newest", "older", "oldest"]);
      const { result } = renderHook(() => useInputHistory());
      let recalled: string | null = null;
      act(() => {
        recalled = result.current.recall("up", "draft");
      });
      expect(recalled).toBe("newest");
    });

    it("should_walk_to_older_entries_on_successive_recall_up_calls", () => {
      seedHistory(["newest", "middle", "oldest"]);
      const { result } = renderHook(() => useInputHistory());
      const recalls: (string | null)[] = [];
      act(() => {
        recalls.push(result.current.recall("up", "draft"));
        recalls.push(result.current.recall("up", "draft"));
        recalls.push(result.current.recall("up", "draft"));
      });
      expect(recalls).toEqual(["newest", "middle", "oldest"]);
    });

    it("should_clamp_at_oldest_entry_when_recall_up_passes_the_end", () => {
      // Past-the-end Ups return the oldest entry (no wrap, no null).
      // Matches bash behavior — keeps the prompt readable.
      seedHistory(["a", "b"]);
      const { result } = renderHook(() => useInputHistory());
      const recalls: (string | null)[] = [];
      act(() => {
        recalls.push(result.current.recall("up", "draft"));
        recalls.push(result.current.recall("up", "draft"));
        recalls.push(result.current.recall("up", "draft"));
        recalls.push(result.current.recall("up", "draft"));
      });
      expect(recalls).toEqual(["a", "b", "b", "b"]);
    });
  });

  describe("recall — Down walks back toward present", () => {
    it("should_walk_toward_present_after_navigating_into_history", () => {
      seedHistory(["newest", "middle", "oldest"]);
      const { result } = renderHook(() => useInputHistory());
      const recalls: (string | null)[] = [];
      act(() => {
        result.current.recall("up", "draft"); // → newest
        result.current.recall("up", "draft"); // → middle
        recalls.push(result.current.recall("down", "draft")); // back to newest
      });
      expect(recalls).toEqual(["newest"]);
    });

    it("should_restore_the_saved_draft_when_walking_past_present_with_recall_down", () => {
      // Draft = text the user had typed before pressing Up the first time.
      // Returning past the newest entry should hand back that draft once.
      seedHistory(["newest"]);
      const { result } = renderHook(() => useInputHistory());
      let restoredDraft: string | null = null;
      act(() => {
        result.current.recall("up", "my draft"); // enter history, save "my draft"
        restoredDraft = result.current.recall("down", "my draft");
      });
      expect(restoredDraft).toBe("my draft");
    });

    it("should_return_null_when_already_at_present_and_recall_down_called_again", () => {
      seedHistory(["x"]);
      const { result } = renderHook(() => useInputHistory());
      let secondDown: string | null = "sentinel";
      act(() => {
        result.current.recall("up", "draft"); // → x
        result.current.recall("down", "draft"); // → "draft" (restored)
        secondDown = result.current.recall("down", "draft"); // → null (no more)
      });
      expect(secondDown).toBeNull();
    });
  });

  describe("reset", () => {
    it("should_reset_pointer_so_next_recall_up_starts_from_latest_again", () => {
      seedHistory(["a", "b", "c"]);
      const { result } = renderHook(() => useInputHistory());
      const recalls: (string | null)[] = [];
      act(() => {
        result.current.recall("up", "draft"); // → a
        result.current.recall("up", "draft"); // → b
        result.current.reset();
        recalls.push(result.current.recall("up", "draft")); // → a (restarted)
      });
      expect(recalls).toEqual(["a"]);
    });
  });

  describe("push", () => {
    it("should_make_pushed_entry_recallable_on_the_next_recall_up", () => {
      const { result } = renderHook(() => useInputHistory());
      act(() => {
        result.current.push("fresh entry");
      });
      let recalled: string | null = null;
      act(() => {
        recalled = result.current.recall("up", "draft");
      });
      expect(recalled).toBe("fresh entry");
    });

    it("should_reset_pointer_so_a_new_push_resumes_from_latest", () => {
      seedHistory(["a"]);
      const { result } = renderHook(() => useInputHistory());
      const recalls: (string | null)[] = [];
      act(() => {
        result.current.recall("up", "draft"); // → a, pointer mid-history
        result.current.push("b"); // resets pointer
        recalls.push(result.current.recall("up", "draft")); // → b (latest)
      });
      expect(recalls).toEqual(["b"]);
    });
  });
});
