import { fireEvent, render, screen } from "@testing-library/react";
import MenuBar from "../index";

jest.mock("@/components/ui/button", () => {
  const React = require("react");
  return {
    Button: React.forwardRef(({ children, unstyled, ...rest }, ref) => (
      <button ref={ref} {...rest}>
        {children}
      </button>
    )),
  };
});
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }) => <div>{children}</div>,
}));
jest.mock("@/components/core/flowSettingsComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="flow-settings" />,
}));
jest.mock(
  "@/controllers/API/queries/flows/use-get-refresh-flows-query",
  () => ({ __esModule: true, useGetRefreshFlowsQuery: () => ({}) }),
);
jest.mock("@/controllers/API/queries/folders/use-get-folders", () => ({
  __esModule: true,
  useGetFoldersQuery: () => ({
    data: [{ id: "f1", name: "Folder" }],
    isFetched: true,
  }),
}));
const mockSave = jest.fn(() => Promise.resolve());
jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSave,
}));
jest.mock("@/hooks/use-unsaved-changes", () => ({
  __esModule: true,
  useUnsavedChanges: () => true,
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  __esModule: true,
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (sel: (s: object) => unknown) =>
    sel({
      autoSaving: false,
      saveLoading: false,
      currentFlow: { updated_at: new Date().toISOString() },
    }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (sel: (s: object) => unknown) => sel({ setSuccessData: jest.fn() }),
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((sel: (s: object) => unknown) =>
    sel({
      onFlowPage: true,
      isBuilding: false,
      currentFlow: {
        id: "1",
        name: "Flow",
        folder_id: "f1",
        icon: "Workflow",
        gradient: "0",
        locked: false,
      },
    }),
  ),
}));
jest.mock("@/stores/shortcuts", () => ({
  __esModule: true,
  useShortcutsStore: (sel: (s: object) => unknown) =>
    sel({ changesSave: "mod+s" }),
}));

// Avoid pulling utils that depend on darkStore
jest.mock("@/utils/utils", () => ({
  __esModule: true,
  cn: (...args: unknown[]) => (args.filter(Boolean) as string[]).join(" "),
  getNumberFromString: () => 0,
}));

jest.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PopoverAnchor: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  PopoverTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  PopoverContent: ({
    children,
    "aria-label": ariaLabel,
  }: {
    children: React.ReactNode;
    "aria-label"?: string;
  }) => (
    <div data-testid="popover-content" aria-label={ariaLabel}>
      {children}
    </div>
  ),
}));

import React from "react";

// styleUtils imports lucide dynamic icons; stub to avoid resolution
jest.mock("lucide-react/dynamicIconImports", () => ({}), { virtual: true });

describe("FlowMenu MenuBar", () => {
  it("renders current folder and flow name, enables save", async () => {
    render(<MenuBar />);
    expect(screen.getByTestId("menu_bar_wrapper")).toBeInTheDocument();
    expect(screen.getByText("Folder")).toBeInTheDocument();
    expect(screen.getByTestId("flow_name").textContent).toBe("Flow");
    expect(screen.getByRole("button", { name: "Folder" })).toHaveClass(
      "focus-visible:ring-1",
    );

    const saveBtn = screen.getByTestId("save-flow-button");
    expect(saveBtn).not.toBeDisabled();
  });

  it("renders flow settings trigger as a named keyboard button", () => {
    render(<MenuBar />);

    const trigger = screen.getByRole("button", {
      name: "Edit flow details and settings for Flow",
    });

    trigger.focus();

    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute("data-testid", "menu_bar_display");
    expect(trigger).toHaveClass("focus-visible:ring-1");
    expect(screen.getByTestId("icon-pencil")).toHaveClass(
      "sm:group-focus-visible:opacity-100",
    );
  });

  it("clicking save calls save flow", () => {
    mockSave.mockClear();
    render(<MenuBar />);
    fireEvent.click(screen.getByTestId("save-flow-button"));
    expect(mockSave).toHaveBeenCalled();
  });

  describe("Accessibility — aria labels", () => {
    const flowStoreMock = jest.requireMock("@/stores/flowStore");

    afterEach(() => {
      flowStoreMock.default.mockReset();
      flowStoreMock.default.mockImplementation((sel: (s: object) => unknown) =>
        sel({
          onFlowPage: true,
          isBuilding: false,
          currentFlow: {
            id: "1",
            name: "Flow",
            folder_id: "f1",
            icon: "Workflow",
            gradient: "0",
            locked: false,
          },
        }),
      );
    });

    it("menu_bar_display is a button element for keyboard and screen reader access", () => {
      render(<MenuBar />);
      const trigger = screen.getByTestId("menu_bar_display");
      expect(trigger.tagName).toBe("BUTTON");
    });

    it("menu_bar_display button has aria-label matching the flow name", () => {
      render(<MenuBar />);
      const trigger = screen.getByTestId("menu_bar_display");
      expect(trigger).toHaveAttribute(
        "aria-label",
        "Edit flow details and settings for Flow",
      );
    });

    it("menu_bar_display aria-label falls back to untitled flow when name is absent", () => {
      flowStoreMock.default.mockImplementation((sel: (s: object) => unknown) =>
        sel({
          onFlowPage: true,
          isBuilding: false,
          currentFlow: {
            id: "1",
            name: undefined,
            folder_id: "f1",
            icon: "Workflow",
            gradient: "0",
            locked: false,
          },
        }),
      );
      render(<MenuBar />);
      const trigger = screen.getByTestId("menu_bar_display");
      expect(trigger).toHaveAttribute(
        "aria-label",
        "Edit flow details and settings for Untitled Flow",
      );
    });

    it("popover content has an aria-label of 'Flow settings' for screen readers", () => {
      render(<MenuBar />);
      const content = screen.getByTestId("popover-content");
      expect(content).toHaveAttribute("aria-label", "Flow settings");
    });
  });
});
