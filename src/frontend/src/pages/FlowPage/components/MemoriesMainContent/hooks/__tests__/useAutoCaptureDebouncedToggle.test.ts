import { act, renderHook } from "@testing-library/react";
import type { MemoryInfo } from "@/controllers/API/queries/memories/types";
import { useAutoCaptureDebouncedToggle } from "../useAutoCaptureDebouncedToggle";

const baseMemory = (overrides?: Partial<MemoryInfo>): MemoryInfo => ({
  id: "m1",
  name: "Memory One",
  description: "",
  kb_name: "kb-1",
  embedding_model: "text-embedding-3-small",
  embedding_provider: "openai",
  is_active: true,
  total_messages_processed: 0,
  sessions_count: 0,
  batch_size: 1,
  preprocessing_enabled: false,
  pending_messages_count: 0,
  user_id: "u1",
  flow_id: "flow-1",
  ...overrides,
});

const flushPending = () => {
  act(() => {
    jest.advanceTimersByTime(500);
  });
};

describe("useAutoCaptureDebouncedToggle", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("fires the debounced mutation with the requested next value", () => {
    const mutate = jest.fn();
    const memory = baseMemory({ is_active: true });

    const { result } = renderHook(() =>
      useAutoCaptureDebouncedToggle({
        memory,
        updateMemoryMutation: { mutate },
      }),
    );

    act(() => {
      result.current.handleToggleActive(false);
    });
    expect(mutate).not.toHaveBeenCalled();

    flushPending();

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0]?.[0]).toEqual({
      memoryId: "m1",
      auto_capture: false,
    });
  });

  it("collapses an on→off→on flip within the debounce window into a no-op", () => {
    const mutate = jest.fn();
    const memory = baseMemory({ is_active: true });

    const { result } = renderHook(() =>
      useAutoCaptureDebouncedToggle({
        memory,
        updateMemoryMutation: { mutate },
      }),
    );

    act(() => {
      result.current.handleToggleActive(false);
      result.current.handleToggleActive(true);
    });
    flushPending();

    expect(mutate).not.toHaveBeenCalled();
  });

  it("invokes onToggleSuccess with the committed value when the mutation resolves", () => {
    const onToggleSuccess = jest.fn();
    const mutate = jest.fn();
    const memory = baseMemory({ is_active: true });

    const { result } = renderHook(() =>
      useAutoCaptureDebouncedToggle({
        memory,
        updateMemoryMutation: { mutate },
        onToggleSuccess,
      }),
    );

    act(() => {
      result.current.handleToggleActive(false);
    });
    flushPending();

    act(() => {
      mutate.mock.calls[0]?.[1]?.onSuccess?.();
    });

    expect(onToggleSuccess).toHaveBeenCalledWith(false);
  });

  it("invokes onToggleError with the attempted value when the mutation fails", () => {
    const onToggleError = jest.fn();
    const mutate = jest.fn();
    const memory = baseMemory({ is_active: false });

    const { result } = renderHook(() =>
      useAutoCaptureDebouncedToggle({
        memory,
        updateMemoryMutation: { mutate },
        onToggleError,
      }),
    );

    act(() => {
      result.current.handleToggleActive(true);
    });
    flushPending();

    act(() => {
      mutate.mock.calls[0]?.[1]?.onError?.();
    });

    expect(onToggleError).toHaveBeenCalledWith(true);
  });

  it("clears any pending timer when the memory id changes", () => {
    const mutate = jest.fn();
    const memoryA = baseMemory({ id: "a", is_active: true });
    const memoryB = baseMemory({ id: "b", is_active: true });

    const { result, rerender } = renderHook(
      ({ memory }) =>
        useAutoCaptureDebouncedToggle({
          memory,
          updateMemoryMutation: { mutate },
        }),
      { initialProps: { memory: memoryA } },
    );

    act(() => {
      result.current.handleToggleActive(false);
    });

    rerender({ memory: memoryB });
    flushPending();

    expect(mutate).not.toHaveBeenCalled();
  });

  it("is a no-op when no memory is selected", () => {
    const mutate = jest.fn();

    const { result } = renderHook(() =>
      useAutoCaptureDebouncedToggle({
        memory: undefined,
        updateMemoryMutation: { mutate },
      }),
    );

    act(() => {
      result.current.handleToggleActive(false);
    });
    flushPending();

    expect(mutate).not.toHaveBeenCalled();
  });
});
