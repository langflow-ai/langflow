import { act, renderHook } from "@testing-library/react";
import type {
  DeploymentProvider,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockCurrentFlowId: string | undefined = "flow-1";

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlow?: { id: string } }) => unknown) =>
    selector({
      currentFlow: mockCurrentFlowId ? { id: mockCurrentFlowId } : undefined,
    }),
}));

const mockSaveFlow = jest.fn();
jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
}));

const mockCreateSnapshot = jest.fn();
jest.mock(
  "@/controllers/API/queries/flow-version/use-post-create-snapshot",
  () => ({
    usePostCreateSnapshot: () => ({
      mutateAsync: mockCreateSnapshot,
    }),
  }),
);

const mockFetchProviders = jest.fn();
jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts",
  () => ({
    useGetProviderAccounts: () => ({
      refetch: mockFetchProviders,
    }),
  }),
);

const mockShowError = jest.fn();
jest.mock(
  "@/pages/MainPage/pages/deploymentsPage/hooks/use-error-alert",
  () => ({
    useErrorAlert: () => mockShowError,
  }),
);

const mockSetSuccessData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: { setSuccessData: jest.Mock }) => unknown) =>
    selector({ setSuccessData: mockSetSuccessData }),
}));

import { usePrepareDeploy } from "../use-prepare-deploy";

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

const makeProvider = (): ProviderAccount => ({
  id: "p1",
  name: "WxO Prod",
  provider_key: "watsonx-orchestrate",
  provider_data: { url: "https://wxo.example.com" },
  created_at: null,
  updated_at: null,
});

const makeDeploymentProvider = (): DeploymentProvider => ({
  id: "watsonx",
  type: "watsonx",
  name: "watsonx Orchestrate",
  icon: "Bot",
});

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  mockCurrentFlowId = "flow-1";
  mockSaveFlow.mockResolvedValue(undefined);
  mockCreateSnapshot.mockResolvedValue({ id: "snap-1", version_tag: "v1.0" });
  mockFetchProviders.mockResolvedValue({ data: { provider_accounts: [] } });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("usePrepareDeploy — initial state", () => {
  it("exposes currentFlowId from flowStore", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    expect(result.current.currentFlowId).toBe("flow-1");
  });

  it("exposes undefined currentFlowId when flow store has no flow", () => {
    mockCurrentFlowId = undefined;
    const { result } = renderHook(() => usePrepareDeploy());

    expect(result.current.currentFlowId).toBeUndefined();
  });

  it("starts with isPreparingDeploy false", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    expect(result.current.isPreparingDeploy).toBe(false);
  });

  it("starts with choiceDialogOpen false", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    expect(result.current.choiceDialogOpen).toBe(false);
  });

  it("starts with deployModalOpen false", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    expect(result.current.deployModalOpen).toBe(false);
  });

  it("starts with empty providers list", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    expect(result.current.providers).toHaveLength(0);
  });
});

describe("usePrepareDeploy — handleDeploy: no flow", () => {
  it("bails early without calling saveFlow when currentFlowId is undefined", async () => {
    mockCurrentFlowId = undefined;
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(mockSaveFlow).not.toHaveBeenCalled();
    expect(mockCreateSnapshot).not.toHaveBeenCalled();
  });

  it("does not open any modal when currentFlowId is undefined", async () => {
    mockCurrentFlowId = undefined;
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.choiceDialogOpen).toBe(false);
    expect(result.current.deployModalOpen).toBe(false);
  });
});

describe("usePrepareDeploy — handleDeploy: no providers", () => {
  it("calls saveFlow before creating snapshot", async () => {
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
  });

  it("calls createSnapshot with the current flowId", async () => {
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(mockCreateSnapshot).toHaveBeenCalledWith({ flowId: "flow-1" });
  });

  it("calls fetchProviderAccounts after snapshot is created", async () => {
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(mockFetchProviders).toHaveBeenCalledTimes(1);
  });

  it("stores snapshot id from createSnapshot result", async () => {
    mockCreateSnapshot.mockResolvedValue({ id: "snap-abc", version_tag: "v2" });
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.pendingSnapshotVersionId).toBe("snap-abc");
  });

  it("builds initialVersionByFlow mapping current flow to snapshot", async () => {
    mockCreateSnapshot.mockResolvedValue({
      id: "snap-xyz",
      version_tag: "v3.0",
    });
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.initialVersionByFlow.get("flow-1")).toEqual({
      versionId: "snap-xyz",
      versionTag: "v3.0",
    });
  });

  it("opens deployModal when providers list is empty", async () => {
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.deployModalOpen).toBe(true);
    expect(result.current.choiceDialogOpen).toBe(false);
  });

  it("resets isPreparingDeploy to false after completion", async () => {
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.isPreparingDeploy).toBe(false);
  });
});

describe("usePrepareDeploy — handleDeploy: with providers", () => {
  it("opens choiceDialog and sets providers when accounts are returned", async () => {
    const providers = [makeProvider()];
    mockFetchProviders.mockResolvedValue({
      data: { provider_accounts: providers },
    });
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.choiceDialogOpen).toBe(true);
    expect(result.current.deployModalOpen).toBe(false);
    expect(result.current.providers).toEqual(providers);
  });

  it("does not open deployModal when providers are available", async () => {
    mockFetchProviders.mockResolvedValue({
      data: { provider_accounts: [makeProvider()] },
    });
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.deployModalOpen).toBe(false);
  });
});

describe("usePrepareDeploy — handleDeploy: error handling", () => {
  it("calls showError when saveFlow throws", async () => {
    mockSaveFlow.mockRejectedValue(new Error("save failed"));
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(mockShowError).toHaveBeenCalledWith(
      "Failed to prepare deployment",
      expect.any(Error),
    );
  });

  it("calls showError when createSnapshot throws", async () => {
    mockCreateSnapshot.mockRejectedValue(new Error("snapshot failed"));
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(mockShowError).toHaveBeenCalledWith(
      "Failed to prepare deployment",
      expect.any(Error),
    );
  });

  it("clears pendingSnapshotVersionId on error", async () => {
    mockCreateSnapshot.mockRejectedValue(new Error("fail"));
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.pendingSnapshotVersionId).toBe("");
  });

  it("resets isPreparingDeploy to false on error", async () => {
    mockSaveFlow.mockRejectedValue(new Error("fail"));
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.isPreparingDeploy).toBe(false);
  });

  it("does not open any modal on error", async () => {
    mockSaveFlow.mockRejectedValue(new Error("fail"));
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });

    expect(result.current.choiceDialogOpen).toBe(false);
    expect(result.current.deployModalOpen).toBe(false);
  });
});

describe("usePrepareDeploy — handleChooseNew", () => {
  it("closes choiceDialog", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    act(() => {
      result.current.setChoiceDialogOpen(true);
    });

    act(() => {
      result.current.handleChooseNew();
    });

    expect(result.current.choiceDialogOpen).toBe(false);
  });

  it("opens deployModal", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    act(() => {
      result.current.handleChooseNew();
    });

    expect(result.current.deployModalOpen).toBe(true);
  });

  it("sets stepperInitialProvider and stepperInitialInstance from preselected", () => {
    const provider = makeDeploymentProvider();
    const instance = makeProvider();
    const { result } = renderHook(() => usePrepareDeploy());

    act(() => {
      result.current.handleChooseNew({ provider, instance });
    });

    expect(result.current.stepperInitialProvider).toEqual(provider);
    expect(result.current.stepperInitialInstance).toEqual(instance);
  });

  it("sets stepperInitialProvider to undefined when no preselected given", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    // First call with a value
    act(() => {
      result.current.handleChooseNew({
        provider: makeDeploymentProvider(),
        instance: makeProvider(),
      });
    });

    // Second call without preselected clears them
    act(() => {
      result.current.handleChooseNew(undefined);
    });

    expect(result.current.stepperInitialProvider).toBeUndefined();
    expect(result.current.stepperInitialInstance).toBeUndefined();
  });
});

describe("usePrepareDeploy — handleUpdateComplete", () => {
  it("closes choiceDialog", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    act(() => {
      result.current.setChoiceDialogOpen(true);
    });

    act(() => {
      result.current.handleUpdateComplete("My Deployment");
    });

    expect(result.current.choiceDialogOpen).toBe(false);
  });

  it("clears providers list", async () => {
    mockFetchProviders.mockResolvedValue({
      data: { provider_accounts: [makeProvider()] },
    });
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });
    expect(result.current.providers).toHaveLength(1);

    act(() => {
      result.current.handleUpdateComplete("My Deployment");
    });

    expect(result.current.providers).toHaveLength(0);
  });

  it("clears pendingSnapshotVersionId", async () => {
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });
    expect(result.current.pendingSnapshotVersionId).toBe("snap-1");

    act(() => {
      result.current.handleUpdateComplete("My Deployment");
    });

    expect(result.current.pendingSnapshotVersionId).toBe("");
  });

  it("shows success notification with the deployment name", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    act(() => {
      result.current.handleUpdateComplete("Sales Bot");
    });

    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: 'Deployment "Sales Bot" updated successfully',
    });
  });
});

describe("usePrepareDeploy — resetChoiceState", () => {
  it("closes choiceDialog", () => {
    const { result } = renderHook(() => usePrepareDeploy());

    act(() => {
      result.current.setChoiceDialogOpen(true);
    });

    act(() => {
      result.current.resetChoiceState();
    });

    expect(result.current.choiceDialogOpen).toBe(false);
  });

  it("clears providers list", async () => {
    mockFetchProviders.mockResolvedValue({
      data: { provider_accounts: [makeProvider()] },
    });
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });
    expect(result.current.providers).toHaveLength(1);

    act(() => {
      result.current.resetChoiceState();
    });

    expect(result.current.providers).toHaveLength(0);
  });

  it("clears pendingSnapshotVersionId", async () => {
    const { result } = renderHook(() => usePrepareDeploy());

    await act(async () => {
      await result.current.handleDeploy();
    });
    expect(result.current.pendingSnapshotVersionId).toBe("snap-1");

    act(() => {
      result.current.resetChoiceState();
    });

    expect(result.current.pendingSnapshotVersionId).toBe("");
  });
});
