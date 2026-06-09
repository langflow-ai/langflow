import { renderHook } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useSanitizeRedirectUrl } from "../use-sanitize-redirect-url";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

describe("useSanitizeRedirectUrl", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it("should call navigate when redirect param exists", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={["/login?redirect=/dashboard"]}>
        <Routes>
          <Route path="/login" element={<div>{children}</div>} />
        </Routes>
      </MemoryRouter>
    );

    renderHook(() => useSanitizeRedirectUrl(), { wrapper });

    // Should call navigate with replace: true
    expect(mockNavigate).toHaveBeenCalledWith(expect.any(String), {
      replace: true,
    });
  });

  it("should not navigate when redirect param does not exist", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<div>{children}</div>} />
        </Routes>
      </MemoryRouter>
    );

    renderHook(() => useSanitizeRedirectUrl(), { wrapper });

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("should handle multiple query params", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter
        initialEntries={["/login?redirect=/dashboard&token=abc123"]}
      >
        <Routes>
          <Route path="/login" element={<div>{children}</div>} />
        </Routes>
      </MemoryRouter>
    );

    renderHook(() => useSanitizeRedirectUrl(), { wrapper });

    expect(mockNavigate).toHaveBeenCalledWith(expect.any(String), {
      replace: true,
    });
  });

  it("should handle paths with no query params", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<div>{children}</div>} />
        </Routes>
      </MemoryRouter>
    );

    renderHook(() => useSanitizeRedirectUrl(), { wrapper });

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("should only run effect once on mount", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={["/login?redirect=/dashboard"]}>
        <Routes>
          <Route path="/login" element={<div>{children}</div>} />
        </Routes>
      </MemoryRouter>
    );

    const { rerender } = renderHook(() => useSanitizeRedirectUrl(), {
      wrapper,
    });

    const initialCallCount = mockNavigate.mock.calls.length;

    rerender();
    rerender();

    // Should not be called again
    expect(mockNavigate).toHaveBeenCalledTimes(initialCallCount);
  });
});
