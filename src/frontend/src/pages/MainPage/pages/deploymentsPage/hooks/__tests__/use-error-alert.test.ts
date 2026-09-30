import { act, renderHook } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSetErrorData = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));

jest.mock("@/controllers/API/helpers/get-axios-error-message", () => ({
  getAxiosErrorMessage: (
    err: unknown,
    fallback = "An unknown error occurred",
  ) => {
    if (err instanceof Error) return err.message;
    return fallback;
  },
}));

import { useErrorAlert } from "../use-error-alert";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useErrorAlert", () => {
  beforeEach(() => {
    mockSetErrorData.mockClear();
  });

  it("calls setErrorData with the provided title and extracted error message", () => {
    const { result } = renderHook(() => useErrorAlert());

    act(() => {
      result.current("Delete failed", new Error("network failure"));
    });

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Delete failed",
      list: ["network failure"],
    });
  });

  it("uses fallback message for non-Error values", () => {
    const { result } = renderHook(() => useErrorAlert());

    act(() => {
      result.current("Oops", "just a string");
    });

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Oops",
      list: ["An unknown error occurred"],
    });
  });

  it("uses fallback message for null errors", () => {
    const { result } = renderHook(() => useErrorAlert());

    act(() => {
      result.current("Error", null);
    });

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Error",
      list: ["An unknown error occurred"],
    });
  });

  it("uses fallback message for undefined errors", () => {
    const { result } = renderHook(() => useErrorAlert());

    act(() => {
      result.current("Error", undefined);
    });

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Error",
      list: ["An unknown error occurred"],
    });
  });

  it("returns a stable callback reference across re-renders", () => {
    const { result, rerender } = renderHook(() => useErrorAlert());
    const first = result.current;

    rerender();

    expect(result.current).toBe(first);
  });

  it("supports different titles and errors in successive calls", () => {
    const { result } = renderHook(() => useErrorAlert());

    act(() => {
      result.current("First error", new Error("error one"));
    });
    act(() => {
      result.current("Second error", new Error("error two"));
    });

    expect(mockSetErrorData).toHaveBeenCalledTimes(2);
    expect(mockSetErrorData).toHaveBeenNthCalledWith(1, {
      title: "First error",
      list: ["error one"],
    });
    expect(mockSetErrorData).toHaveBeenNthCalledWith(2, {
      title: "Second error",
      list: ["error two"],
    });
  });
});
