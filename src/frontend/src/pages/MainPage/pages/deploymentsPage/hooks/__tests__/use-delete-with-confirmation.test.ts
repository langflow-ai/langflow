import { act, renderHook } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockShowError = jest.fn();

jest.mock("../use-error-alert", () => ({
  useErrorAlert: () => mockShowError,
}));

import { useDeleteWithConfirmation } from "../use-delete-with-confirmation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface TestItem {
  id: string;
  name: string;
}

type Params = { id: string };

const makeEvent = () =>
  ({
    stopPropagation: jest.fn(),
  }) as unknown as React.MouseEvent<HTMLButtonElement, MouseEvent>;

const renderDeleteHook = (
  mutateFn: jest.Mock = jest.fn(),
  buildParams: (id: string) => Params = (id) => ({ id }),
  errorMessage = "Failed to delete item",
) =>
  renderHook(() =>
    useDeleteWithConfirmation<TestItem, Params>(
      mutateFn,
      buildParams,
      errorMessage,
    ),
  );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDeleteWithConfirmation", () => {
  beforeEach(() => {
    mockShowError.mockClear();
  });

  describe("initial state", () => {
    it("initializes with null target", () => {
      const { result } = renderDeleteHook();
      expect(result.current.target).toBeNull();
    });

    it("initializes with null deletingId", () => {
      const { result } = renderDeleteHook();
      expect(result.current.deletingId).toBeNull();
    });
  });

  describe("requestDelete", () => {
    it("sets the target item", () => {
      const { result } = renderDeleteHook();
      const item: TestItem = { id: "item-1", name: "Widget" };

      act(() => {
        result.current.requestDelete(item);
      });

      expect(result.current.target).toEqual(item);
    });

    it("replaces a previous target with the new one", () => {
      const { result } = renderDeleteHook();

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "First" });
      });
      act(() => {
        result.current.requestDelete({ id: "item-2", name: "Second" });
      });

      expect(result.current.target).toEqual({ id: "item-2", name: "Second" });
    });
  });

  describe("cancelDelete", () => {
    it("clears the target", () => {
      const { result } = renderDeleteHook();

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.cancelDelete();
      });

      expect(result.current.target).toBeNull();
    });

    it("is a no-op when target is already null", () => {
      const { result } = renderDeleteHook();

      act(() => {
        result.current.cancelDelete();
      });

      expect(result.current.target).toBeNull();
    });
  });

  describe("setModalOpen", () => {
    it("clears the target when called with false", () => {
      const { result } = renderDeleteHook();

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.setModalOpen(false);
      });

      expect(result.current.target).toBeNull();
    });

    it("does not change state when called with true", () => {
      const { result } = renderDeleteHook();
      const item: TestItem = { id: "item-1", name: "Widget" };

      act(() => {
        result.current.requestDelete(item);
      });
      act(() => {
        result.current.setModalOpen(true);
      });

      expect(result.current.target).toEqual(item);
    });
  });

  describe("confirmDelete", () => {
    it("does nothing when target is null", () => {
      const mutateFn = jest.fn();
      const { result } = renderDeleteHook(mutateFn);
      const event = makeEvent();

      act(() => {
        result.current.confirmDelete(event);
      });

      expect(mutateFn).not.toHaveBeenCalled();
    });

    it("calls stopPropagation on the event", () => {
      const { result } = renderDeleteHook();
      const event = makeEvent();

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.confirmDelete(event);
      });

      expect(event.stopPropagation).toHaveBeenCalled();
    });

    it("calls mutateFn with params built from the target id", () => {
      const mutateFn = jest.fn();
      const buildParams = jest.fn((id: string) => ({ id, extra: "data" }));
      const { result } = renderDeleteHook(mutateFn, buildParams);
      const item: TestItem = { id: "item-1", name: "Widget" };

      act(() => {
        result.current.requestDelete(item);
      });
      act(() => {
        result.current.confirmDelete(makeEvent());
      });

      expect(buildParams).toHaveBeenCalledWith("item-1");
      expect(mutateFn).toHaveBeenCalledWith(
        { id: "item-1", extra: "data" },
        expect.objectContaining({
          onError: expect.any(Function),
          onSettled: expect.any(Function),
        }),
      );
    });

    it("sets deletingId to the confirmed item's id", () => {
      const mutateFn = jest.fn();
      const { result } = renderDeleteHook(mutateFn);

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.confirmDelete(makeEvent());
      });

      expect(result.current.deletingId).toBe("item-1");
    });

    it("clears target after confirming", () => {
      const { result } = renderDeleteHook();

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.confirmDelete(makeEvent());
      });

      expect(result.current.target).toBeNull();
    });
  });

  describe("mutation callbacks", () => {
    it("onSettled clears deletingId", () => {
      const mutateFn = jest.fn();
      const { result } = renderDeleteHook(mutateFn);

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.confirmDelete(makeEvent());
      });
      expect(result.current.deletingId).toBe("item-1");

      act(() => {
        const { onSettled } = mutateFn.mock.calls[0][1] as {
          onSettled: () => void;
        };
        onSettled();
      });

      expect(result.current.deletingId).toBeNull();
    });

    it("onError calls showError with the configured error message", () => {
      const mutateFn = jest.fn();
      const { result } = renderDeleteHook(
        mutateFn,
        (id) => ({ id }),
        "Cannot delete widget",
      );

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.confirmDelete(makeEvent());
      });

      const error = new Error("server error");
      act(() => {
        const { onError } = mutateFn.mock.calls[0][1] as {
          onError: (err: unknown) => void;
        };
        onError(error);
      });

      expect(mockShowError).toHaveBeenCalledWith("Cannot delete widget", error);
    });

    it("onError can handle non-Error values", () => {
      const mutateFn = jest.fn();
      const { result } = renderDeleteHook(mutateFn);

      act(() => {
        result.current.requestDelete({ id: "item-1", name: "Widget" });
      });
      act(() => {
        result.current.confirmDelete(makeEvent());
      });

      act(() => {
        const { onError } = mutateFn.mock.calls[0][1] as {
          onError: (err: unknown) => void;
        };
        onError("a plain string error");
      });

      expect(mockShowError).toHaveBeenCalledWith(
        "Failed to delete item",
        "a plain string error",
      );
    });
  });
});
