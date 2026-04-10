import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import type { Deployment } from "../../types";
import { useTestDeploymentModal } from "../use-test-deployment-modal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeDeployment = (overrides: Partial<Deployment> = {}): Deployment =>
  ({
    id: "dep-1",
    name: "My Deployment",
    provider_account_id: "prov-1",
    ...overrides,
  }) as Deployment;

const withRouter =
  (
    initialEntries: Array<string | { pathname: string; state?: unknown }> = [
      "/",
    ],
  ) =>
  ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
  );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useTestDeploymentModal", () => {
  describe("initial state", () => {
    it("starts with no test target and modal closed", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      expect(result.current.testTarget).toBeNull();
      expect(result.current.open).toBe(false);
      expect(result.current.testProviderId).toBe("");
    });
  });

  describe("handleTestDeployment", () => {
    it("sets testTarget from the deployment", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });
      const deployment = makeDeployment({
        id: "d1",
        name: "Bot",
        provider_account_id: "p1",
      });

      act(() => {
        result.current.handleTestDeployment(deployment);
      });

      expect(result.current.testTarget).toMatchObject({
        id: "d1",
        name: "Bot",
      });
    });

    it("sets testProviderId from deployment.provider_account_id", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      act(() => {
        result.current.handleTestDeployment(
          makeDeployment({ provider_account_id: "prov-99" }),
        );
      });

      expect(result.current.testProviderId).toBe("prov-99");
    });

    it("uses empty string for testProviderId when provider_account_id is null", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      act(() => {
        result.current.handleTestDeployment(
          makeDeployment({ provider_account_id: null as unknown as string }),
        );
      });

      expect(result.current.testProviderId).toBe("");
    });

    it("opens the modal", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      act(() => {
        result.current.handleTestDeployment(makeDeployment());
      });

      expect(result.current.open).toBe(true);
    });
  });

  describe("handleTestFromStepper", () => {
    it("sets testTarget and testProviderId from explicit args", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      act(() => {
        result.current.handleTestFromStepper(
          { id: "d2", name: "Stepper Bot" },
          "stepper-provider",
        );
      });

      expect(result.current.testTarget).toEqual({
        id: "d2",
        name: "Stepper Bot",
      });
      expect(result.current.testProviderId).toBe("stepper-provider");
      expect(result.current.open).toBe(true);
    });
  });

  describe("close", () => {
    it("clears testTarget and testProviderId", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      act(() => {
        result.current.handleTestDeployment(makeDeployment());
      });
      act(() => {
        result.current.close();
      });

      expect(result.current.testTarget).toBeNull();
      expect(result.current.testProviderId).toBe("");
      expect(result.current.open).toBe(false);
    });
  });

  describe("setOpen", () => {
    it("clears testTarget and testProviderId when called with false", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      act(() => {
        result.current.handleTestDeployment(makeDeployment());
      });
      act(() => {
        result.current.setOpen(false);
      });

      expect(result.current.testTarget).toBeNull();
      expect(result.current.testProviderId).toBe("");
    });

    it("does not change state when called with true", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      act(() => {
        result.current.setOpen(true);
      });

      expect(result.current.testTarget).toBeNull();
    });
  });

  describe("auto-open from navigation state", () => {
    it("opens modal and sets target when navigated from canvas deploy button", async () => {
      const initialState = {
        testDeployment: { id: "nav-dep", name: "Nav Bot" },
        testProviderId: "nav-provider",
      };

      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter([{ pathname: "/all", state: initialState }]),
      });

      await waitFor(() => {
        expect(result.current.testTarget).toEqual({
          id: "nav-dep",
          name: "Nav Bot",
        });
      });

      expect(result.current.testProviderId).toBe("nav-provider");
      expect(result.current.open).toBe(true);
    });

    it("does not auto-open when navigation state has testDeployment but no testProviderId", async () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter([
          {
            pathname: "/all",
            state: { testDeployment: { id: "d1", name: "Bot" } },
          },
        ]),
      });

      // Give the effect time to run
      await act(async () => {
        await Promise.resolve();
      });

      expect(result.current.testTarget).toBeNull();
      expect(result.current.open).toBe(false);
    });

    it("does not auto-open when navigation state has testProviderId but no testDeployment", async () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter([
          { pathname: "/all", state: { testProviderId: "p1" } },
        ]),
      });

      await act(async () => {
        await Promise.resolve();
      });

      expect(result.current.testTarget).toBeNull();
      expect(result.current.open).toBe(false);
    });

    it("does not auto-open when navigation state is empty", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter([{ pathname: "/all", state: {} }]),
      });

      expect(result.current.testTarget).toBeNull();
      expect(result.current.open).toBe(false);
    });
  });

  describe("open computed property", () => {
    it("is true only when testTarget is set", () => {
      const { result } = renderHook(() => useTestDeploymentModal(), {
        wrapper: withRouter(),
      });

      expect(result.current.open).toBe(false);

      act(() => {
        result.current.handleTestDeployment(makeDeployment());
      });
      expect(result.current.open).toBe(true);

      act(() => {
        result.current.close();
      });
      expect(result.current.open).toBe(false);
    });
  });
});
