import type { GlobalVariable } from "@/types/global_variables";
import {
  authorizedVariableIds,
  canMutateVariable,
  canShareVariable,
  formatVariableValue,
} from "../variableAccess";

const variable = (patch: Partial<GlobalVariable> = {}): GlobalVariable => ({
  id: "variable-1",
  name: "TOKEN",
  type: "Credential",
  default_fields: [],
  is_owner: false,
  can_manage_shares: false,
  ...patch,
});

const loaded = {
  isLoading: false,
  isError: false,
  permissions: { "variable-1": ["read", "write", "delete"] },
};

describe("shared variable UI policy", () => {
  it("never displays a shared credential or generic value", () => {
    expect(
      formatVariableValue(variable({ value: "secret" }), "secret", "Hidden"),
    ).toBe("Hidden");
    expect(
      formatVariableValue(
        variable({ type: "Generic", value: "plain" }),
        "plain",
        "Hidden",
      ),
    ).toBe("Hidden");
  });

  it("fails closed while permissions load and hides re-share from recipients", () => {
    const allow = jest.fn(() => true);
    expect(
      canMutateVariable(
        variable(),
        "write",
        { ...loaded, isLoading: true },
        allow,
      ),
    ).toBe(false);
    expect(canShareVariable(variable())).toBe(false);
    expect(allow).not.toHaveBeenCalled();
  });

  it("fails closed for shared rows on errors or unevaluated ids", () => {
    const allow = jest.fn(() => true);
    expect(
      canMutateVariable(
        variable(),
        "write",
        { ...loaded, isError: true },
        allow,
      ),
    ).toBe(false);
    expect(
      canMutateVariable(
        variable(),
        "delete",
        { ...loaded, permissions: {} },
        allow,
      ),
    ).toBe(false);
    expect(allow).not.toHaveBeenCalled();
  });

  it("lets an authorized owner mutate and manage shares", () => {
    const owned = variable({ is_owner: true, can_manage_shares: true });
    expect(canMutateVariable(owned, "delete", loaded, () => true)).toBe(true);
    expect(canShareVariable(owned)).toBe(true);
  });

  it("revalidates retained selections and drops missing or revoked rows", () => {
    const variables = [
      variable({ id: "allowed" }),
      variable({ id: "revoked", name: "REVOKED" }),
    ];
    const state = {
      ...loaded,
      permissions: {
        allowed: ["read", "delete"],
        revoked: ["read"],
      },
    };

    expect(
      authorizedVariableIds(
        ["allowed", "revoked", "removed"],
        variables,
        "delete",
        state,
        (id, action) => state.permissions[id]?.includes(action) === true,
      ),
    ).toEqual(["allowed"]);
  });

  it("fails closed when a retained shared selection becomes unevaluated", () => {
    expect(
      authorizedVariableIds(
        ["variable-1"],
        [variable()],
        "delete",
        { ...loaded, permissions: undefined },
        () => true,
      ),
    ).toEqual([]);
  });
});
