import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
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
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (sel) => sel({ setSuccessData: mockSetSuccessData }),
}));

let mockSetCurrentFlow = jest.fn();
const mockAutoSaveFlush = jest.fn();
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
      autoSaveFlow: { flush: (...args) => mockAutoSaveFlush(...args) },
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
  });

  it("renders and disables save when no changes", () => {
    render(<FlowSettingsComponent flowData={baseFlow} open close={() => {}} />);
    const saveBtn = screen.getByTestId("save-flow-settings");
    expect(saveBtn).toBeDisabled();
  });

  it("enables save when name changes and autoSaving true triggers saveFlow and success", async () => {
    mockAutoSaving = true;
    mockSave.mockResolvedValueOnce(undefined);
    const onClose = jest.fn();

    render(<FlowSettingsComponent flowData={baseFlow} open close={onClose} />);

    fireEvent.click(screen.getByTestId("set-name-new"));
    const saveBtn = screen.getByTestId("save-flow-settings");
    expect(saveBtn).not.toBeDisabled();

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockAutoSaveFlush).toHaveBeenCalled();
      expect(mockSave).toHaveBeenCalledWith(
        expect.objectContaining({ name: "New Name" }),
      );
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "Changes saved successfully",
      });
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("flushes a pending canvas autosave before saving settings", async () => {
    mockAutoSaving = true;
    mockAutoSaveFlush.mockReset();
    mockSave.mockReset();
    let releaseAutoSave: () => void = () => {};
    mockAutoSaveFlush.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        releaseAutoSave = resolve;
      }),
    );
    mockSave.mockResolvedValueOnce(undefined);

    render(<FlowSettingsComponent flowData={baseFlow} open close={() => {}} />);

    fireEvent.click(screen.getByTestId("toggle-lock"));
    fireEvent.click(screen.getByTestId("save-flow-settings"));

    await waitFor(() => expect(mockAutoSaveFlush).toHaveBeenCalled());
    expect(mockSave).not.toHaveBeenCalled();

    releaseAutoSave();

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledWith(
        expect.objectContaining({ locked: true }),
      );
    });
    expect(mockAutoSaveFlush.mock.invocationCallOrder[0]).toBeLessThan(
      mockSave.mock.invocationCallOrder[0],
    );
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

  it("clicking cancel calls close", () => {
    const onClose = jest.fn();
    render(<FlowSettingsComponent flowData={baseFlow} open close={onClose} />);
    fireEvent.click(screen.getByTestId("cancel-flow-settings"));
    expect(onClose).toHaveBeenCalled();
  });
});
