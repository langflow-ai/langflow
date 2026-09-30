import { act, renderHook } from "@testing-library/react";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";
import { useAutoCaptureDebouncedToggle } from "../useAutoCaptureDebouncedToggle";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: unknown) => unknown) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMemory(overrides: Partial<MemoryInfo> = {}): MemoryInfo {
  return {
    id: "m1",
    name: "Test Memory",
    kb_name: "",
    embedding_model: "",
    embedding_provider: "",
    is_active: false,
    total_messages_processed: 0,
    sessions_count: 0,
    batch_size: 1,
    preprocessing_enabled: false,
    pending_messages_count: 0,
    user_id: "u1",
    flow_id: "flow-1",
    ...overrides,
  };
}

function makeProps(
  memory: MemoryInfo | undefined,
  mutate = jest.fn(),
  debounceMs = 0,
) {
  return {
    memory,
    updateMemoryMutation: { mutate },
    debounceMs,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe("useAutoCaptureDebouncedToggle", () => {
  describe("initial state", () => {
    it("returns null draft on mount", () => {
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(makeMemory())),
      );
      expect(result.current.autoCaptureDraft).toBeNull();
    });
  });

  describe("handleToggleActive — no-ops", () => {
    it("does nothing when memory is undefined", () => {
      const mutate = jest.fn();
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(undefined, mutate)),
      );
      act(() => result.current.handleToggleActive(true));
      jest.runAllTimers();
      expect(mutate).not.toHaveBeenCalled();
      expect(result.current.autoCaptureDraft).toBeNull();
    });

    it("does nothing when toggling to the same value as current state", () => {
      const mutate = jest.fn();
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(false));
      jest.runAllTimers();
      expect(mutate).not.toHaveBeenCalled();
      expect(result.current.autoCaptureDraft).toBeNull();
    });
  });

  describe("handleToggleActive — optimistic draft", () => {
    it("sets autoCaptureDraft immediately before debounce fires", () => {
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, jest.fn(), 500)),
      );
      act(() => result.current.handleToggleActive(true));
      expect(result.current.autoCaptureDraft).toBe(true);
    });

    it("accepts an updater function and derives next value from current state", () => {
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, jest.fn(), 500)),
      );
      act(() => result.current.handleToggleActive((prev) => !prev));
      expect(result.current.autoCaptureDraft).toBe(true);
    });
  });

  describe("handleToggleActive — debounce and mutation", () => {
    it("calls mutate with correct args after debounce", () => {
      const mutate = jest.fn();
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(true));
      act(() => jest.runAllTimers());
      expect(mutate).toHaveBeenCalledWith(
        { memoryId: "m1", auto_capture: true },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        }),
      );
    });

    it("debounces rapid successive toggles — only one mutate call", () => {
      const mutate = jest.fn();
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate, 200)),
      );
      act(() => {
        result.current.handleToggleActive(true);
        jest.advanceTimersByTime(100);
        result.current.handleToggleActive(true);
      });
      act(() => jest.runAllTimers());
      expect(mutate).toHaveBeenCalledTimes(1);
    });

    it("cancels pending mutation when toggling back to committed value", () => {
      const mutate = jest.fn();
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate, 200)),
      );
      act(() => {
        result.current.handleToggleActive(true);
        jest.advanceTimersByTime(100);
        // toggle back before debounce fires
        result.current.handleToggleActive(false);
      });
      act(() => jest.runAllTimers());
      expect(mutate).not.toHaveBeenCalled();
      expect(result.current.autoCaptureDraft).toBeNull();
    });
  });

  describe("toast notifications", () => {
    it("shows success toast with memory name when enabled", () => {
      const mutate = jest.fn((_, opts) => opts?.onSuccess?.());
      const memory = makeMemory({ is_active: false, name: "My Memory" });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(true));
      act(() => jest.runAllTimers());
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: 'Auto-capture enabled for memory "My Memory"',
      });
    });

    it("shows success toast with memory name when disabled", () => {
      const mutate = jest.fn((_, opts) => opts?.onSuccess?.());
      const memory = makeMemory({ is_active: true, name: "My Memory" });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(false));
      act(() => jest.runAllTimers());
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: 'Auto-capture disabled for memory "My Memory"',
      });
    });

    it("shows error toast when mutation fails", () => {
      const mutate = jest.fn((_, opts) =>
        opts?.onError?.(new Error("api error")),
      );
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(true));
      act(() => jest.runAllTimers());
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Failed to update auto-capture",
        list: ["api error"],
      });
    });

    it("shows exactly one error toast on failure — no duplicate from mutation level", () => {
      const mutate = jest.fn((_, opts) =>
        opts?.onError?.(new Error("api error")),
      );
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(true));
      act(() => jest.runAllTimers());
      expect(mockSetErrorData).toHaveBeenCalledTimes(1);
    });
  });

  describe("draft cleanup", () => {
    it("clears draft on mutation success", () => {
      const mutate = jest.fn((_, opts) => opts?.onSuccess?.());
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(true));
      act(() => jest.runAllTimers());
      expect(result.current.autoCaptureDraft).toBeNull();
    });

    it("clears draft on mutation error", () => {
      const mutate = jest.fn((_, opts) =>
        opts?.onError?.(new Error("api error")),
      );
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );
      act(() => result.current.handleToggleActive(true));
      act(() => jest.runAllTimers());
      expect(result.current.autoCaptureDraft).toBeNull();
    });

    it("snaps back to original memory.is_active after mutation failure", () => {
      const mutate = jest.fn((_, opts) =>
        opts?.onError?.(new Error("api error")),
      );
      // Start with is_active = false, toggle to true, then fail
      const memory = makeMemory({ is_active: false });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );

      // Draft goes to true optimistically
      act(() => result.current.handleToggleActive(true));
      expect(result.current.autoCaptureDraft).toBe(true);

      // Mutation fires and fails — draft must clear, reverting to original false
      act(() => jest.runAllTimers());
      expect(result.current.autoCaptureDraft).toBeNull();
      // null draft means the UI falls back to memory.is_active (false) — original value restored
    });

    it("snaps back correctly when toggling an active memory to inactive and failing", () => {
      const mutate = jest.fn((_, opts) =>
        opts?.onError?.(new Error("api error")),
      );
      const memory = makeMemory({ is_active: true });
      const { result } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate)),
      );

      act(() => result.current.handleToggleActive(false));
      expect(result.current.autoCaptureDraft).toBe(false);

      act(() => jest.runAllTimers());
      expect(result.current.autoCaptureDraft).toBeNull();
      // null draft means the UI falls back to memory.is_active (true) — original value restored
    });

    it("resets all state when memory id changes", () => {
      const mutate = jest.fn();
      const memory = makeMemory({ is_active: false });
      const { result, rerender } = renderHook(
        (props) => useAutoCaptureDebouncedToggle(props),
        { initialProps: makeProps(memory, mutate, 500) },
      );
      act(() => result.current.handleToggleActive(true));
      expect(result.current.autoCaptureDraft).toBe(true);

      rerender(makeProps(makeMemory({ id: "m2", name: "Other" }), mutate, 500));
      expect(result.current.autoCaptureDraft).toBeNull();
    });

    it("cancels pending timer on unmount", () => {
      const mutate = jest.fn();
      const memory = makeMemory({ is_active: false });
      const { result, unmount } = renderHook(() =>
        useAutoCaptureDebouncedToggle(makeProps(memory, mutate, 500)),
      );
      act(() => result.current.handleToggleActive(true));
      unmount();
      act(() => jest.runAllTimers());
      expect(mutate).not.toHaveBeenCalled();
    });
  });
});
