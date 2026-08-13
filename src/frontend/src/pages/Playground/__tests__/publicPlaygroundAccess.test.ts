import { canOpenPublicPlayground } from "../publicPlaygroundAccess";

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
