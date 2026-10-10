import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { FlowSaveBlockedError } from "@/hooks/flows/save-blocked-error";
import useFlowConflictStore from "@/stores/flowConflictStore";
import type { FlowType } from "@/types/flow";
import FlowSettingsComponent from "../index";

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, loading, ...rest }) => (
    <button {...rest}>{children}</button>
  ),
}));

// Simplify Radix Form to a native form that respects onSubmit
type MockFormRootProps = {
  children: React.ReactNode;
  onSubmit?: React.FormEventHandler<HTMLFormElement>;
};

jest.mock("@radix-ui/react-form", () => ({
  __esModule: true,
  Root: React.forwardRef<HTMLFormElement, MockFormRootProps>(
    ({ children, onSubmit }, ref) => (
      <form onSubmit={onSubmit} ref={ref}>
        {children}
      </form>
    ),
  ),
  Submit: ({ asChild, children }) => {
    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(
        children as React.ReactElement<{ type?: "submit" }>,
        { type: "submit" },
      );
    }
    return <button type="submit">Submit</button>;
  },
}));

const mockSave = jest.fn();
jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSave,
}));

let mockSetSuccessData = jest.fn();
const mockSetNoticeData = jest.fn();
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => {
  const alerts = () => ({
    setSuccessData: mockSetSuccessData,
    setNoticeData: mockSetNoticeData,
    setErrorData: mockSetErrorData,
  });
  const useAlertStore = (sel) => sel(alerts());
  useAlertStore.getState = alerts;
  return { __esModule: true, default: useAlertStore };
});

let mockSetCurrentFlow = jest.fn();
const mockAutoSaveFlush = jest.fn();
const mockAutoSaveEnqueue = jest.fn();
let mockHasEditorAutoSave = true;
jest.mock("@/stores/flowStore", () => {
  const useFlowStore = (sel) =>
    sel({
      currentFlow: {
        id: "1",
        name: "Flow",
        description: "Desc",
        locked: false,
      },
      setCurrentFlow: (...args) => mockSetCurrentFlow(...args),
      autoSaveFlow: mockHasEditorAutoSave
        ? {
            flush: (...args) => mockAutoSaveFlush(...args),
            enqueue: (...args) => mockAutoSaveEnqueue(...args),
          }
        : undefined,
    });
  return {
    __esModule: true,
    default: useFlowStore,
  };
});

let mockAutoSaving = false;
let mockFlows: Array<{ name: string }> = [];
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (sel) => sel({ autoSaving: mockAutoSaving, flows: mockFlows }),
}));

// Mock EditFlowSettings to expose simple controls that call the provided setters
jest.mock("@/components/core/editFlowSettingsComponent", () => ({
  __esModule: true,
  default: ({
    setName,
    setDescription,
    setLocked,
  }: {
    setName?: (v: string) => void;
    setDescription?: (v: string) => void;
    setLocked?: (v: boolean) => void;
  }) => (
    <div>
      <button
        type="button"
        data-testid="set-name-new"
        onClick={() => setName?.("New Name")}
      >
        set name
      </button>
      <button
        type="button"
        data-testid="set-name-taken"
        onClick={() => setName?.("Taken")}
      >
        set taken
      </button>
      <button
        type="button"
        data-testid="set-desc-new"
        onClick={() => setDescription?.("New Desc")}
      >
        set desc
      </button>
      <button
        type="button"
        data-testid="toggle-lock"
        onClick={() => setLocked?.(true)}
      >
        toggle lock
      </button>
    </div>
  ),
}));

describe("FlowSettingsComponent", () => {
  const baseFlow = {
    id: "1",
    name: "Flow",
    description: "Desc",
    locked: false,
  } as FlowType;

  beforeEach(() => {
    jest.clearAllMocks();
    mockAutoSaving = false;
    mockFlows = [{ name: "Flow" }, { name: "Other" }];
    mockSetSuccessData = jest.fn();
    mockSetCurrentFlow = jest.fn();
    mockAutoSaveFlush.mockResolvedValue(undefined);
    mockAutoSaveEnqueue.mockResolvedValue(undefined);
    mockHasEditorAutoSave = true;
  });

  it("renders and disables save when no changes", () => {
    render(<FlowSettingsComponent flowData={baseFlow} open close={() => {}} />);
    const saveBtn = screen.getByTestId("save-flow-settings");
    expect(saveBtn).toBeDisabled();
  });

  it("enables save when name changes and autoSaving true queues the save and reports success", async () => {
    mockAutoSaving = true;
    const onClose = jest.fn();

    render(<FlowSettingsComponent open close={onClose} />);

    fireEvent.click(screen.getByTestId("set-name-new"));
    const saveBtn = screen.getByTestId("save-flow-settings");
    expect(saveBtn).not.toBeDisabled();

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockAutoSaveEnqueue).toHaveBeenCalledWith(
        expect.objectContaining({ name: "New Name" }),
      );
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "Changes saved successfully",
      });
      expect(onClose).toHaveBeenCalled();
    });
    expect(mockSave).not.toHaveBeenCalled();
  });

  it("saves the lock through the editor's save queue", async () => {
    // A canvas autosave queued while the lock save is in flight must run after
    // it; run alongside, it carries locked:false and the server rejects it.
    mockAutoSaving = true;
    let releaseSettingsSave: () => void = () => {};
    mockAutoSaveEnqueue.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        releaseSettingsSave = resolve;
      }),
    );
    const onClose = jest.fn();

    render(<FlowSettingsComponent open close={onClose} />);

    fireEvent.click(screen.getByTestId("toggle-lock"));
    fireEvent.click(screen.getByTestId("save-flow-settings"));

    await waitFor(() =>
      expect(mockAutoSaveEnqueue).toHaveBeenCalledWith(
        expect.objectContaining({ locked: true }),
      ),
    );
    expect(onClose).not.toHaveBeenCalled();

    releaseSettingsSave();

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(mockSave).not.toHaveBeenCalled();
  });

  it("saves directly when no editor autosave is registered", async () => {
    mockAutoSaving = true;
    mockHasEditorAutoSave = false;
    mockSave.mockResolvedValueOnce(undefined);
    const onClose = jest.fn();

    render(<FlowSettingsComponent flowData={baseFlow} open close={onClose} />);

    fireEvent.click(screen.getByTestId("toggle-lock"));
    fireEvent.click(screen.getByTestId("save-flow-settings"));

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledWith(
        expect.objectContaining({ locked: true }),
      );
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("saves a flow card directly even when an editor autosave is registered", async () => {
    // The registered autosave may belong to an editor that has unmounted; its
    // save never settles, which left the home page modal spinning.
    mockAutoSaving = true;
    mockSave.mockResolvedValueOnce(undefined);
    const onClose = jest.fn();

    render(<FlowSettingsComponent flowData={baseFlow} open close={onClose} />);

    fireEvent.click(screen.getByTestId("set-name-new"));
    fireEvent.click(screen.getByTestId("save-flow-settings"));

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledWith(
        expect.objectContaining({ name: "New Name" }),
      );
      expect(onClose).toHaveBeenCalled();
    });
    expect(mockAutoSaveEnqueue).not.toHaveBeenCalled();
  });

  it("keeps the modal open when the queued save fails", async () => {
    mockAutoSaving = true;
    mockAutoSaveEnqueue.mockRejectedValueOnce(new Error("boom"));
    const onClose = jest.fn();

    render(<FlowSettingsComponent open close={onClose} />);

    fireEvent.click(screen.getByTestId("toggle-lock"));
    fireEvent.click(screen.getByTestId("save-flow-settings"));

    await waitFor(() => expect(mockAutoSaveEnqueue).toHaveBeenCalled());
    expect(onClose).not.toHaveBeenCalled();
    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  it("non-autoSaving path sets current flow and closes", () => {
    mockAutoSaving = false;
    const onClose = jest.fn();

    render(<FlowSettingsComponent flowData={baseFlow} open close={onClose} />);

    fireEvent.click(screen.getByTestId("set-desc-new"));
    const saveBtn = screen.getByTestId("save-flow-settings");
    expect(saveBtn).not.toBeDisabled();
    fireEvent.click(saveBtn);

    expect(mockSetCurrentFlow).toHaveBeenCalledWith(
      expect.objectContaining({ description: "New Desc" }),
    );
    expect(onClose).toHaveBeenCalled();
  });

  it("prevents saving when name is taken", () => {
    mockFlows = [{ name: "Taken" }, { name: "Flow" }];

    render(<FlowSettingsComponent flowData={baseFlow} open close={() => {}} />);

    fireEvent.click(screen.getByTestId("set-name-taken"));
    expect(screen.getByTestId("save-flow-settings")).toBeDisabled();
  });

  describe("when the save does not happen", () => {
    afterEach(() => {
      useFlowConflictStore.setState({ conflict: null, dialogOpen: false });
    });

    const submitRename = async (onClose: jest.Mock) => {
      render(
        <FlowSettingsComponent flowData={baseFlow} open close={onClose} />,
      );
      fireEvent.click(screen.getByTestId("set-name-new"));
      fireEvent.click(screen.getByTestId("save-flow-settings"));
      await waitFor(() => expect(mockSave).toHaveBeenCalled());
    };

    it("stays open and says why when a conflict blocks the save", async () => {
      mockAutoSaving = true;
      useFlowConflictStore.setState({
        conflict: {
          flowId: "1",
          author: { id: "user-2", username: "carlos" },
          isSelf: false,
          modifiedAt: null,
          expectedToken: "a",
          currentToken: "b",
          theirFlow: null,
        },
      });
      mockSave.mockRejectedValueOnce(new FlowSaveBlockedError("1"));
      const onClose = jest.fn();

      await submitRename(onClose);

      await waitFor(() => expect(mockSetNoticeData).toHaveBeenCalled());
      expect(onClose).not.toHaveBeenCalled();
      expect(mockSetSuccessData).not.toHaveBeenCalled();
    });

    it("stays open when the save fails for another reason", async () => {
      mockAutoSaving = true;
      mockSave.mockRejectedValueOnce(new Error("network down"));
      const onClose = jest.fn();

      await submitRename(onClose);

      await waitFor(() =>
        expect(screen.getByTestId("save-flow-settings")).toBeInTheDocument(),
      );
      expect(onClose).not.toHaveBeenCalled();
      expect(mockSetSuccessData).not.toHaveBeenCalled();
    });
  });

  it("clicking cancel calls close", () => {
    const onClose = jest.fn();
    render(<FlowSettingsComponent flowData={baseFlow} open close={onClose} />);
    fireEvent.click(screen.getByTestId("cancel-flow-settings"));
    expect(onClose).toHaveBeenCalled();
  });
});
