import { renderHook } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockNavigate = jest.fn();

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

import { useNavigateToTest } from "../use-navigate-to-test";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useNavigateToTest", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it("navigates to /all with flowType, testDeployment, and testProviderId in state", () => {
    const { result } = renderHook(() => useNavigateToTest());

    result.current({ id: "d1", name: "My Deployment" }, "provider-1");

    expect(mockNavigate).toHaveBeenCalledWith("/all", {
      state: {
        flowType: "deployments",
        testDeployment: { id: "d1", name: "My Deployment" },
        testProviderId: "provider-1",
      },
    });
  });

  it("passes the correct deployment id and name to state", () => {
    const { result } = renderHook(() => useNavigateToTest());

    result.current({ id: "abc-123", name: "Production Bot" }, "wxo-prod");

    expect(mockNavigate).toHaveBeenCalledWith(
      "/all",
      expect.objectContaining({
        state: expect.objectContaining({
          testDeployment: { id: "abc-123", name: "Production Bot" },
        }),
      }),
    );
  });

  it("passes the correct provider id to state", () => {
    const { result } = renderHook(() => useNavigateToTest());

    result.current({ id: "d1", name: "Bot" }, "my-provider-id");

    expect(mockNavigate).toHaveBeenCalledWith(
      "/all",
      expect.objectContaining({
        state: expect.objectContaining({ testProviderId: "my-provider-id" }),
      }),
    );
  });

  it("always navigates to /all regardless of deployment details", () => {
    const { result } = renderHook(() => useNavigateToTest());

    result.current({ id: "d2", name: "Another Bot" }, "p2");

    expect(mockNavigate).toHaveBeenCalledWith("/all", expect.anything());
  });

  it("always sets flowType to 'deployments'", () => {
    const { result } = renderHook(() => useNavigateToTest());

    result.current({ id: "d1", name: "Bot" }, "p1");

    const [[, options]] = mockNavigate.mock.calls;
    expect(options.state.flowType).toBe("deployments");
  });

  it("returns a stable callback reference across re-renders", () => {
    const { result, rerender } = renderHook(() => useNavigateToTest());
    const first = result.current;

    rerender();

    expect(result.current).toBe(first);
  });
});
