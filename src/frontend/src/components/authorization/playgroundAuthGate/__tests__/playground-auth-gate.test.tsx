/**
 * Tests for PlaygroundAuthGate decision logic.
 *
 * The gate protects the /playground/:id/ route by holding the page in a loading
 * state until the session has hydrated, then rendering it.
 *
 * It deliberately does NOT decide public access. It used to send any
 * unauthenticated visitor to /login whenever auto-login was disabled, which made
 * public direct links unreachable for anonymous visitors on exactly the
 * deployments where anonymity is meaningful — the page never got to ask the
 * server whether the flow was public. That decision now belongs to the page,
 * which asks the server and routes to /login (with this URL preserved) only
 * once the link is known to be unusable.
 *
 * These tests import the real implementation rather than re-deriving it, so a
 * change to the gate's contract has to change this file too.
 */

import { renderHook } from "@testing-library/react";
import { computePlaygroundAuthState } from "../authState";

describe("computePlaygroundAuthState", () => {
  describe("Anonymous visitors (the public direct-link audience)", () => {
    it("admits an anonymous visitor once the auth check completes", () => {
      // The regression this guards: an anonymous visitor on a login-required
      // deployment must still reach the page so the public flow can load.
      expect(
        computePlaygroundAuthState({
          isAuthenticated: false,
          isAutoLoginFetched: true,
          isSessionProcessed: true,
        }),
      ).toBe("allowed");
    });

    it("does not accept autoLogin as an input at all", () => {
      // Structural guard: re-introducing an auto-login-keyed redirect would
      // have to widen this signature, which fails this assertion.
      expect(computePlaygroundAuthState).toHaveLength(1);
      expect(
        computePlaygroundAuthState({
          isAuthenticated: false,
          isAutoLoginFetched: true,
          isSessionProcessed: true,
          // @ts-expect-error autoLogin is intentionally not part of the contract
          autoLogin: false,
        }),
      ).toBe("allowed");
    });
  });

  describe("Authenticated visitors", () => {
    it("admits an authenticated visitor", () => {
      expect(
        computePlaygroundAuthState({
          isAuthenticated: true,
          isAutoLoginFetched: true,
          isSessionProcessed: true,
        }),
      ).toBe("allowed");
    });

    it("admits an authenticated visitor before the auto-login probe settles", () => {
      // isAuthenticated=true completes the auth check on its own.
      expect(
        computePlaygroundAuthState({
          isAuthenticated: true,
          isAutoLoginFetched: false,
          isSessionProcessed: true,
        }),
      ).toBe("allowed");
    });
  });

  describe("Loading states", () => {
    it("waits while nothing has settled", () => {
      expect(
        computePlaygroundAuthState({
          isAuthenticated: false,
          isAutoLoginFetched: false,
          isSessionProcessed: false,
        }),
      ).toBe("loading");
    });

    it("waits while the session check is pending", () => {
      // The visitor may still hold a valid cookie; deciding now would be wrong.
      expect(
        computePlaygroundAuthState({
          isAuthenticated: false,
          isAutoLoginFetched: true,
          isSessionProcessed: false,
        }),
      ).toBe("loading");
    });

    it("waits while the auto-login probe is pending and nobody is signed in", () => {
      expect(
        computePlaygroundAuthState({
          isAuthenticated: false,
          isAutoLoginFetched: false,
          isSessionProcessed: true,
        }),
      ).toBe("loading");
    });
  });

  describe("State transitions", () => {
    it("moves from loading to allowed when the session restores auth", () => {
      const { result, rerender } = renderHook(
        (props: {
          isAuthenticated: boolean;
          isAutoLoginFetched: boolean;
          isSessionProcessed: boolean;
        }) => computePlaygroundAuthState(props),
        {
          initialProps: {
            isAuthenticated: false,
            isAutoLoginFetched: true,
            isSessionProcessed: false,
          },
        },
      );

      expect(result.current).toBe("loading");

      rerender({
        isAuthenticated: true,
        isAutoLoginFetched: true,
        isSessionProcessed: true,
      });

      expect(result.current).toBe("allowed");
    });

    it("moves from loading to allowed for a visitor who never authenticates", () => {
      const { result, rerender } = renderHook(
        (props: {
          isAuthenticated: boolean;
          isAutoLoginFetched: boolean;
          isSessionProcessed: boolean;
        }) => computePlaygroundAuthState(props),
        {
          initialProps: {
            isAuthenticated: false,
            isAutoLoginFetched: false,
            isSessionProcessed: false,
          },
        },
      );

      expect(result.current).toBe("loading");

      // Auto-login probe rejects (403) and the session says "not signed in" —
      // previously a redirect to /login, now an admitted anonymous visitor.
      rerender({
        isAuthenticated: false,
        isAutoLoginFetched: true,
        isSessionProcessed: true,
      });

      expect(result.current).toBe("allowed");
    });
  });
});
