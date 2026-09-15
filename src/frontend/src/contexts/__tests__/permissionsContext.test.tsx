import { fireEvent, render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";

const mockUseGetEffectivePermissions = jest.fn();
const mockUseGetAuthorizationCapabilities = jest.fn();
jest.mock("@/controllers/API/queries/permissions", () => ({
  useGetEffectivePermissions: (...args: unknown[]) =>
    mockUseGetEffectivePermissions(...args),
}));
jest.mock("@/controllers/API/queries/authorization", () => ({
  useGetAuthorizationCapabilities: (...args: unknown[]) =>
    mockUseGetAuthorizationCapabilities(...args),
}));

import {
  PermissionsProvider,
  useIsFlowPermissionPending,
  useIsFlowReadOnly,
  usePermissions,
  useResourceCapability,
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

function setMockedCapabilities(
  enforcementActive = true,
  flags?: { isLoading?: boolean; isError?: boolean },
) {
  mockUseGetAuthorizationCapabilities.mockReturnValue({
    data: flags?.isLoading
      ? undefined
      : {
          enforcement_active: enforcementActive,
          service_ready: true,
          team_roles_supported: true,
          user_team_sharing_supported: true,
          share_modes: ["execute", "write"],
          conditional_writes_required: true,
          can_administer_platform: false,
          can_create_team: false,
        },
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
  it("fails closed when no provider resolved authorization", () => {
    const { result } = renderHook(() => usePermissions());
    expect(result.current.can("flow-1", "delete")).toBe(false);
    expect(result.current.permissions).toBeUndefined();
    expect(result.current.isUnavailable).toBe(true);
  });
});

describe("PermissionsProvider gating", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setMockedCapabilities();
  });

  it.each(["permissions error", "capabilities error", "unready", "loading"])(
    "denies cached grants after %s",
    (failure) => {
      const permissionQuery = {
        data: {
          permissions: { "flow-1": ["read", "write"] },
          capabilities: { "flow-1": { can_edit: true } },
        },
        isLoading: false,
        isError: false,
      };
      mockUseGetEffectivePermissions.mockReturnValue(permissionQuery);
      const { result, rerender } = renderHook(
        () => ({
          provider: usePermissions(),
          resource: useResourceCapability("flow", "flow-1", "can_edit"),
        }),
        { wrapper: flowWrapper(["flow-1"]) },
      );
      expect(result.current.provider.can("flow-1", "write")).toBe(true);
      expect(result.current.resource.allowed).toBe(true);

      const authorizationQuery = mockUseGetAuthorizationCapabilities();
      if (failure === "permissions error") permissionQuery.isError = true;
      if (failure === "capabilities error") authorizationQuery.isError = true;
      if (failure === "unready") {
        mockUseGetAuthorizationCapabilities.mockReturnValue({
          ...authorizationQuery,
          data: { ...authorizationQuery.data, service_ready: false },
        });
      }
      if (failure === "loading") permissionQuery.isLoading = true;
      rerender();

      expect(result.current.provider.can("flow-1", "write")).toBe(false);
      expect(result.current.provider.capability("flow-1", "can_edit")).toBe(
        false,
      );
      expect(result.current.provider.isUnavailable).toBe(true);
      expect(result.current.resource.allowed).toBe(false);
      expect(result.current.resource.isUnavailable).toBe(true);
    },
  );

  it("keeps every action enabled when the pass-through returns all actions", () => {
    setMockedPermissions({
      "flow-1": ["read", "write", "execute", "delete", "create"],
    });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current.can("flow-1", "delete")).toBe(true);
    expect(result.current.can("flow-1", "write")).toBe(true);
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

  it("fails closed while the request is still loading", () => {
    setMockedPermissions(undefined, { isLoading: true });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current.can("flow-1", "delete")).toBe(false);
  });

  it("uses the fallback only when the server disables enforcement", () => {
    setMockedPermissions(undefined, { isError: true });
    setMockedCapabilities(false);
    const { result } = renderHook(() => usePermissions(), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current.can("flow-1", "delete")).toBe(true);
    expect(result.current.capability("flow-1", "can_manage_shares")).toBe(true);
  });

  it("can preserve the previous permission map while resource ids change", () => {
    setMockedPermissions({ "flow-1": ["read"] });

    renderHook(() => usePermissions(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <PermissionsProvider
          resourceType="flow"
          resourceIds={["flow-1"]}
          preservePreviousPermissions
        >
          {children}
        </PermissionsProvider>
      ),
    });

    expect(mockUseGetEffectivePermissions).toHaveBeenCalledWith(
      expect.objectContaining({ resourceIds: ["flow-1"] }),
      { placeholderData: expect.any(Function) },
    );
    const queryOptions = mockUseGetEffectivePermissions.mock.calls[0][1] as {
      placeholderData: (previousData: unknown) => unknown;
    };
    const previousData = { resource_type: "flow", permissions: {} };
    expect(queryOptions.placeholderData(previousData)).toBe(previousData);
  });
});

describe("useIsFlowReadOnly", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setMockedCapabilities();
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

  it("fails closed without a provider", () => {
    const { result } = renderHook(() => useIsFlowReadOnly("flow-1"));
    expect(result.current).toBe(true);
  });
});

describe("useIsFlowPermissionPending", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setMockedCapabilities();
  });

  it("is true while flow permissions are loading", () => {
    setMockedPermissions(undefined, { isLoading: true });
    const { result } = renderHook(() => useIsFlowPermissionPending("flow-1"), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current).toBe(true);
  });

  it("clears once the answer arrives, even when write is denied", () => {
    setMockedPermissions({ "flow-1": ["read"] });
    const { result } = renderHook(() => useIsFlowPermissionPending("flow-1"), {
      wrapper: flowWrapper(["flow-1"]),
    });
    // Read-only stays true here; pending is the transient half and must not
    // outlive the query, or a denied user would see "checking" forever.
    expect(result.current).toBe(false);
  });

  it("is false when write permission is allowed", () => {
    setMockedPermissions({ "flow-1": ["read", "write"] });
    const { result } = renderHook(() => useIsFlowPermissionPending("flow-1"), {
      wrapper: flowWrapper(["flow-1"]),
    });
    expect(result.current).toBe(false);
  });

  it("is false without a flow id even while the provider resolves", () => {
    setMockedPermissions(undefined, { isLoading: true });
    const { result } = renderHook(() => useIsFlowPermissionPending(undefined), {
      wrapper: flowWrapper([]),
    });
    expect(result.current).toBe(false);
  });

  it("is false without a provider because unavailable is not loading", () => {
    const { result } = renderHook(() => useIsFlowPermissionPending("flow-1"));
    expect(result.current).toBe(false);
  });

  it("tracks useIsFlowReadOnly while loading and diverges after", () => {
    setMockedPermissions(undefined, { isLoading: true });
    const loading = renderHook(
      () => ({
        readOnly: useIsFlowReadOnly("flow-1"),
        pending: useIsFlowPermissionPending("flow-1"),
      }),
      { wrapper: flowWrapper(["flow-1"]) },
    );
    expect(loading.result.current).toEqual({ readOnly: true, pending: true });

    setMockedPermissions({ "flow-1": ["read"] });
    const resolved = renderHook(
      () => ({
        readOnly: useIsFlowReadOnly("flow-1"),
        pending: useIsFlowPermissionPending("flow-1"),
      }),
      { wrapper: flowWrapper(["flow-1"]) },
    );
    expect(resolved.result.current).toEqual({ readOnly: true, pending: false });
  });
});

describe("component affordance gating", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setMockedCapabilities();
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
