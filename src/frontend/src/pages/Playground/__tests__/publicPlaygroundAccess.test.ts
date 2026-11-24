import {
  canOpenPublicPlayground,
  unreachablePlaygroundDestination,
} from "../publicPlaygroundAccess";

describe("canOpenPublicPlayground", () => {
  it("opens a PRIVATE flow that carries a canonical public execute share", () => {
    // The reported regression: the backend authorizes this flow anonymously,
    // but the legacy flag alone sent the visitor back to /flows.
    expect(
      canOpenPublicPlayground({
        access_type: "PRIVATE",
        public_access: { can_read: true, can_execute: true },
      }),
    ).toBe(true);
  });

  it("does not offer execution for a read-only public share", () => {
    expect(
      canOpenPublicPlayground({
        access_type: "PRIVATE",
        public_access: { can_read: true, can_execute: false },
      }),
    ).toBe(false);
  });

  it("lets a read-only share bound a flow whose legacy flag is still PUBLIC", () => {
    expect(
      canOpenPublicPlayground({
        access_type: "PUBLIC",
        public_access: { can_read: true, can_execute: false },
      }),
    ).toBe(false);
  });

  it("keeps the legacy PUBLIC flag working when no capability set is present", () => {
    expect(canOpenPublicPlayground({ access_type: "PUBLIC" })).toBe(true);
  });

  it("refuses a PRIVATE flow with neither a share nor the legacy flag", () => {
    expect(canOpenPublicPlayground({ access_type: "PRIVATE" })).toBe(false);
  });

  it("refuses a missing flow", () => {
    expect(canOpenPublicPlayground(undefined)).toBe(false);
    expect(canOpenPublicPlayground(null)).toBe(false);
  });
});

describe("unreachablePlaygroundDestination", () => {
  const flowId = "8f14e45f-ceea-467a-9f7f-1f0e2a7c0c1a";

  it("sends an anonymous visitor to sign in and keeps the link as the target", () => {
    // The route gate used to do this unconditionally, which is what made public
    // links unreachable. Now it only happens once the server declines the flow.
    expect(
      unreachablePlaygroundDestination({
        flowId,
        autoLogin: false,
        isAuthenticated: false,
      }),
    ).toBe(`/login?redirect=/playground/${flowId}/`);
  });

  it("sends a signed-in visitor home", () => {
    expect(
      unreachablePlaygroundDestination({
        flowId,
        autoLogin: false,
        isAuthenticated: true,
      }),
    ).toBe("/");
  });

  it("sends an auto-login deployment home", () => {
    expect(
      unreachablePlaygroundDestination({
        flowId,
        autoLogin: true,
        isAuthenticated: false,
      }),
    ).toBe("/");
  });

  it("sends home while auth state is still hydrating", () => {
    // autoLogin is null before the probe settles; guessing "sign in" here would
    // bounce visitors off deployments that do not require a session at all.
    expect(
      unreachablePlaygroundDestination({
        flowId,
        autoLogin: null,
        isAuthenticated: false,
      }),
    ).toBe("/");
  });

  it("sends home when there is no flow id to come back to", () => {
    expect(
      unreachablePlaygroundDestination({
        flowId: undefined,
        autoLogin: false,
        isAuthenticated: false,
      }),
    ).toBe("/");
  });
});
