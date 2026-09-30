import { act, renderHook } from "@testing-library/react";
import { useDeleteWithConfirmation } from "../use-delete-with-confirmation";

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockShowError = jest.fn();

jest.mock("../use-error-alert", () => ({
  useErrorAlert: () => mockShowError,
}));

// ── Helpers ────────────────────────────────────────────────────────────────

type Item = { id: string; name: string };

const makeItem = (overrides: Partial<Item> = {}): Item => ({
  id: "dep-1",
  name: "My Deployment",
  ...overrides,
});

const buildParams = (id: string) => ({ deployment_id: id });

function makeMouseEvent() {
  return { stopPropagation: jest.fn() } as unknown as React.MouseEvent<
    HTMLButtonElement,
    MouseEvent
  >;
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("useDeleteWithConfirmation", () => {
  let mutateFn: jest.Mock;

  beforeEach(() => {
    mutateFn = jest.fn();
    mockShowError.mockClear();
  });

  it("starts with target and deletingId as null", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );

    expect(result.current.target).toBeNull();
    expect(result.current.deletingId).toBeNull();
  });

  it("requestDelete sets the target item", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );
    const item = makeItem();

    act(() => {
      result.current.requestDelete(item);
    });

    expect(result.current.target).toEqual(item);
  });

  it("requestDelete replaces a previous target with the new one", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );

    act(() => {
      result.current.requestDelete(makeItem({ id: "dep-1", name: "First" }));
    });
    act(() => {
      result.current.requestDelete(makeItem({ id: "dep-2", name: "Second" }));
    });

    expect(result.current.target).toEqual({ id: "dep-2", name: "Second" });
  });

  it("confirmDelete calls mutateFn with built params and clears target", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );
    const item = makeItem();

    act(() => {
      result.current.requestDelete(item);
    });

    act(() => {
      result.current.confirmDelete(makeMouseEvent());
    });

    expect(mutateFn).toHaveBeenCalledWith(
      { deployment_id: "dep-1" },
      expect.objectContaining({
        onError: expect.any(Function),
        onSettled: expect.any(Function),
      }),
    );
    expect(result.current.target).toBeNull();
    expect(result.current.deletingId).toBe("dep-1");
  });

  it("confirmDelete calls stopPropagation on the event", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );
    const event = makeMouseEvent();

    act(() => {
      result.current.requestDelete(makeItem());
    });
    act(() => {
      result.current.confirmDelete(event);
    });

    expect(event.stopPropagation).toHaveBeenCalled();
  });

  it("confirmDelete is a no-op when target is null", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );

    act(() => {
      result.current.confirmDelete(makeMouseEvent());
    });

    expect(mutateFn).not.toHaveBeenCalled();
  });

  it("onSettled clears deletingId", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );

    act(() => {
      result.current.requestDelete(makeItem());
    });
    act(() => {
      result.current.confirmDelete(makeMouseEvent());
    });

    expect(result.current.deletingId).toBe("dep-1");

    const { onSettled } = mutateFn.mock.calls[0][1];
    act(() => {
      onSettled();
    });

    expect(result.current.deletingId).toBeNull();
  });

  it("onError calls showError with the configured message", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(
        mutateFn,
        buildParams,
        "Error deleting deployment",
      ),
    );

    act(() => {
      result.current.requestDelete(makeItem());
    });
    act(() => {
      result.current.confirmDelete(makeMouseEvent());
    });

    const { onError } = mutateFn.mock.calls[0][1];
    const fakeError = new Error("network failure");
    act(() => {
      onError(fakeError);
    });

    expect(mockShowError).toHaveBeenCalledWith(
      "Error deleting deployment",
      fakeError,
    );
  });

  it("onError handles non-Error values", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Failed to delete item"),
    );

    act(() => {
      result.current.requestDelete(makeItem());
    });
    act(() => {
      result.current.confirmDelete(makeMouseEvent());
    });

    const { onError } = mutateFn.mock.calls[0][1];
    act(() => {
      onError("a plain string error");
    });

    expect(mockShowError).toHaveBeenCalledWith(
      "Failed to delete item",
      "a plain string error",
    );
  });

  it("setModalOpen(false) clears the target", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );

    act(() => {
      result.current.requestDelete(makeItem());
    });
    expect(result.current.target).not.toBeNull();

    act(() => {
      result.current.setModalOpen(false);
    });

    expect(result.current.target).toBeNull();
  });

  it("setModalOpen(true) does not change target", () => {
    const { result } = renderHook(() =>
      useDeleteWithConfirmation(mutateFn, buildParams, "Error"),
    );

    act(() => {
      result.current.requestDelete(makeItem());
    });

    act(() => {
      result.current.setModalOpen(true);
    });

    expect(result.current.target).toEqual(makeItem());
  });
});
