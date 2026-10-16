import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import PublishDropdown from "../deploy-dropdown";

const mockAutoSaveFlush = jest.fn();
const mockMutateAsync = jest.fn();
const mockSetCurrentFlow = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetFlows = jest.fn();
const mockCurrentFlow = {
  id: "flow-1",
  name: "Flow",
  folder_id: "project-1",
  access_type: "PRIVATE",
};
const mockWriteText = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("react-router-dom", () => ({
  useHref: () => "/",
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: React.ComponentProps<"button">) => (
    <button {...props}>{children}</button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuItem: ({
    children,
    onSelect,
    disabled: _disabled,
    ...props
  }: React.ComponentProps<"div"> & {
    disabled?: boolean;
    onSelect?: (event: Event) => void;
  }) => (
    <div
      {...props}
      role="menuitem"
      tabIndex={-1}
      onClick={() => onSelect?.(new Event("select"))}
      onKeyDown={() => onSelect?.(new Event("select"))}
    >
      {children}
    </div>
  ),
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

jest.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    onClick,
    ...props
  }: React.ComponentProps<"button"> & { checked?: boolean }) => (
    <button
      {...props}
      aria-checked={checked}
      onClick={onClick}
      role="switch"
      type="button"
    />
  ),
}));

jest.mock("@/contexts/permissionsContext", () => ({
  usePermissions: () => ({ can: () => true }),
}));

jest.mock("@/controllers/API/queries/flows/use-patch-update-flow", () => ({
  usePatchUpdateFlow: () => ({ mutateAsync: mockMutateAsync }),
}));

jest.mock("@/customization/components/custom-flow-share-action", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/customization/components/custom-link", () => ({
  CustomLink: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_PUBLISH: true,
  ENABLE_WIDGET: false,
}));

jest.mock("@/customization/utils/custom-mcp-open", () => ({
  customMcpOpen: () => undefined,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...values: Array<string | false | null | undefined>) =>
    values.filter(Boolean).join(" "),
}));

jest.mock("@/modals/apiModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/modals/EmbedModal/embed-modal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/modals/exportModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector) => selector({ setErrorData: mockSetErrorData }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector) => selector({ autoLogin: true }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector) =>
    selector({
      autoSaveFlow: { flush: mockAutoSaveFlush },
      hasIO: true,
      setCurrentFlow: mockSetCurrentFlow,
    }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector) =>
    selector({
      currentFlow: mockCurrentFlow,
      flows: [mockCurrentFlow],
      setFlows: mockSetFlows,
    }),
}));

Object.defineProperty(navigator, "clipboard", {
  configurable: true,
  value: { writeText: mockWriteText },
});

describe("PublishDropdown", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCurrentFlow.access_type = "PRIVATE";
    mockAutoSaveFlush.mockResolvedValue(undefined);
    mockMutateAsync.mockResolvedValue(undefined);
    mockWriteText.mockResolvedValue(undefined);
  });

  it("shows the full shareable link with a single slash when sharing is on", () => {
    mockCurrentFlow.access_type = "PUBLIC";

    render(<PublishDropdown openApiModal={false} setOpenApiModal={() => {}} />);

    expect(screen.getByTestId("shareable-playground-url")).toHaveTextContent(
      "http://localhost/playground/flow-1",
    );
  });

  it("copies the shareable link in one click", async () => {
    mockCurrentFlow.access_type = "PUBLIC";

    render(<PublishDropdown openApiModal={false} setOpenApiModal={() => {}} />);
    fireEvent.click(screen.getByTestId("copy-shareable-playground-url"));

    await waitFor(() =>
      expect(mockWriteText).toHaveBeenCalledWith(
        "http://localhost/playground/flow-1",
      ),
    );
    expect(
      await screen.findByText("misc.shareableLinkCopied"),
    ).toBeInTheDocument();
  });

  it("offers no link to copy while sharing is off", () => {
    render(<PublishDropdown openApiModal={false} setOpenApiModal={() => {}} />);

    expect(
      screen.queryByTestId("copy-shareable-playground-url"),
    ).not.toBeInTheDocument();
  });

  it("flushes pending canvas edits before publishing the flow", async () => {
    let releaseAutoSave: () => void = () => {};
    mockAutoSaveFlush.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        releaseAutoSave = resolve;
      }),
    );

    render(<PublishDropdown openApiModal={false} setOpenApiModal={() => {}} />);

    fireEvent.click(screen.getByTestId("publish-switch"));

    await waitFor(() => expect(mockAutoSaveFlush).toHaveBeenCalledTimes(1));
    expect(mockMutateAsync).not.toHaveBeenCalled();

    releaseAutoSave();

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith(
        { id: "flow-1", access_type: "PUBLIC" },
        expect.any(Object),
      );
    });
    expect(mockAutoSaveFlush.mock.invocationCallOrder[0]).toBeLessThan(
      mockMutateAsync.mock.invocationCallOrder[0],
    );
  });
});
