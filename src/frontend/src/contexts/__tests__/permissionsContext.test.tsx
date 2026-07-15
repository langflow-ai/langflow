import { fireEvent, render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";

const mockUseGetEffectivePermissions = jest.fn();
jest.mock("@/controllers/API/queries/permissions", () => ({
  useGetEffectivePermissions: (...args: unknown[]) =>
    mockUseGetEffectivePermissions(...args),
}));

import {
  PermissionsProvider,
  useIsFlowReadOnly,
  usePermissions,
} from "../permissionsContext";

function setMockedPermissions(
  permissions: Record<string, string[]> | undefined,
  flags?: { isLoading?: boolean; isError?: boolean },
) {
  mockUseGetEffectivePermissions.mockReturnValue({
    data: permissions ? { resource_type: "flow", permissions } : undefined,
    isLoading: flags?.isLoading ?? false,
    isError: flags?.isError ?? false,
  });
}

function flowWrapper(resourceIds: string[]) {
  return ({ children }: { children: ReactNode }) => (
    <PermissionsProvider resourceType="flow" resourceIds={resourceIds}>
      {children}
    </PermissionsProvider>
  );
}

describe("usePermissions without a provider", () => {
  it("fail-opens: can() always returns true", () => {
    const { result } = renderHook(() => usePermissions());
    expect(result.current.can("flow-1", "delete")).toBe(true);
    expect(result.current.permissions).toBeUndefined();
  });
});

describe("PermissionsProvider gating", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("keeps every action enabled when the pass-through returns all actions", () => {
    setMockedPermissions({
      "flow-1": ["read", "write", "execute", "delete", "create", "deploy"],
    });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current.can("flow-1", "delete")).toBe(true);
    expect(result.current.can("flow-1", "write")).toBe(true);
    expect(result.current.can("flow-1", "deploy")).toBe(true);
  });

  it("gates actions that the response omits for a resource", () => {
    setMockedPermissions({ "flow-1": ["read"] });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current.can("flow-1", "read")).toBe(true);
    expect(result.current.can("flow-1", "delete")).toBe(false);
    expect(result.current.can("flow-1", "write")).toBe(false);
  });

  it("fail-opens while the request is still loading", () => {
    setMockedPermissions(undefined, { isLoading: true });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current.can("flow-1", "delete")).toBe(true);
  });
});

describe("useIsFlowReadOnly", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("fails closed while flow permissions are loading", () => {
    setMockedPermissions(undefined, { isLoading: true });
    const { result } = renderHook(() => useIsFlowReadOnly("flow-1"), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current).toBe(true);
  });

  it("returns true when write permission is denied", () => {
    setMockedPermissions({ "flow-1": ["read"] });
    const { result } = renderHook(() => useIsFlowReadOnly("flow-1"), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current).toBe(true);
  });

  it("returns false when write permission is allowed", () => {
    setMockedPermissions({ "flow-1": ["read", "write"] });
    const { result } = renderHook(() => useIsFlowReadOnly("flow-1"), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current).toBe(false);
  });

  it("keeps the non-RBAC fallback writable without a provider", () => {
    const { result } = renderHook(() => useIsFlowReadOnly("flow-1"));
    expect(result.current).toBe(false);
  });
});

describe("component affordance gating", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  function DeleteButton({ onDelete }: { onDelete: () => void }) {
    const { can } = usePermissions();
    return (
      <button
        type="button"
        disabled={!can("flow-1", "delete")}
        onClick={onDelete}
        data-testid="delete-btn"
      >
        Delete
      </button>
    );
  }

  it("disables a denied control and does not fire its handler on click", () => {
    setMockedPermissions({ "flow-1": ["read"] });
    const onDelete = jest.fn();
    render(
      <PermissionsProvider resourceType="flow" resourceIds={["flow-1"]}>
        <DeleteButton onDelete={onDelete} />
      </PermissionsProvider>,
    );
    const button = screen.getByTestId("delete-btn") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("enables an allowed control and fires its handler on click", () => {
    setMockedPermissions({ "flow-1": ["read", "delete"] });
    const onDelete = jest.fn();
    render(
      <PermissionsProvider resourceType="flow" resourceIds={["flow-1"]}>
        <DeleteButton onDelete={onDelete} />
      </PermissionsProvider>,
    );
    const button = screen.getByTestId("delete-btn") as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    expect(onDelete).toHaveBeenCalledTimes(1);
  });
});
