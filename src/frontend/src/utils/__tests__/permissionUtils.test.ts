import { buildPermissionMap, canPerformAction } from "../permissionUtils";

describe("buildPermissionMap", () => {
  it("returns undefined for null/undefined responses (unresolved sentinel)", () => {
    expect(buildPermissionMap(undefined)).toBeUndefined();
    expect(buildPermissionMap(null)).toBeUndefined();
  });

  it("returns undefined when the response has no permissions field", () => {
    expect(
      buildPermissionMap({} as Parameters<typeof buildPermissionMap>[0]),
    ).toBeUndefined();
  });

  it("lowercases resource ids and actions", () => {
    const map = buildPermissionMap({
      permissions: { "ABC-123": ["READ", "Write"] },
    });
    expect(map).toEqual({ "abc-123": ["read", "write"] });
  });

  it("preserves an empty action list as a deny-all entry", () => {
    expect(buildPermissionMap({ permissions: { x: [] } })).toEqual({ x: [] });
  });
});

describe("canPerformAction", () => {
  it("fails closed when the map is undefined", () => {
    expect(canPerformAction(undefined, "id", "delete")).toBe(false);
  });

  it("fails closed when the resource id is missing or empty", () => {
    expect(canPerformAction({ id: [] }, undefined, "read")).toBe(false);
    expect(canPerformAction({ id: [] }, null, "read")).toBe(false);
    expect(canPerformAction({ id: [] }, "", "read")).toBe(false);
  });

  it("fails closed when the resource id was not evaluated", () => {
    expect(canPerformAction({ other: ["read"] }, "id", "read")).toBe(false);
  });

  it("allows unresolved state only for an explicit disabled-enforcement fallback", () => {
    expect(canPerformAction(undefined, "id", "read", true)).toBe(true);
    expect(canPerformAction({ other: ["read"] }, "id", "read", true)).toBe(
      true,
    );
  });

  it("allows an action listed for a present resource", () => {
    expect(canPerformAction({ id: ["read", "write"] }, "id", "write")).toBe(
      true,
    );
  });

  it("denies an action absent from a present resource's list", () => {
    expect(canPerformAction({ id: ["read"] }, "id", "delete")).toBe(false);
  });

  it("denies every action when the resource's list is empty", () => {
    expect(canPerformAction({ id: [] }, "id", "read")).toBe(false);
  });

  it("is case-insensitive on both the id and the action", () => {
    expect(canPerformAction({ "abc-123": ["read"] }, "ABC-123", "READ")).toBe(
      true,
    );
  });
});
