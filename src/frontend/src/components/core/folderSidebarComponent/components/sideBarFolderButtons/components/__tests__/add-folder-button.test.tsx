import { fireEvent, render, screen } from "@testing-library/react";
import type { ProjectTypeType } from "@/pages/MainPage/entities";
import { AddFolderButton } from "../add-folder-button";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    "aria-label": ariaLabel,
    disabled,
    loading,
    ...props
  }: {
    children: React.ReactNode;
    "aria-label"?: string;
    disabled?: boolean;
    loading?: boolean;
    [key: string]: unknown;
  }) => (
    <button
      aria-label={ariaLabel}
      disabled={disabled}
      data-loading={loading}
      {...props}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DropdownMenuItem: ({
    children,
    onSelect,
    ...props
  }: {
    children: React.ReactNode;
    onSelect?: () => void;
    [key: string]: unknown;
  }) => (
    <button type="button" onClick={onSelect} {...props}>
      {children}
    </button>
  ),
}));

describe("AddFolderButton", () => {
  const defaultProps = { onClick: jest.fn(), disabled: false, loading: false };
  const FLOWS: ProjectTypeType = {
    name: "flows",
    display_name: "Flows",
    icon: "Folders",
    description: "A plain project.",
    template: {},
  };
  const HARNESS: ProjectTypeType = {
    name: "agent-harness",
    display_name: "Agent Harness",
    icon: "Bot",
    description: "An agent built from the flows in this project.",
    template: {},
  };

  it("renders the add project button", () => {
    render(<AddFolderButton {...defaultProps} />);
    expect(screen.getByTestId("add-project-button")).toBeInTheDocument();
  });

  it("has an aria-label for screen readers", () => {
    render(<AddFolderButton {...defaultProps} />);
    const btn = screen.getByTestId("add-project-button");
    expect(btn).toHaveAttribute("aria-label", "folder.createNewProject");
  });

  it("is disabled when disabled prop is true", () => {
    render(<AddFolderButton {...defaultProps} disabled />);
    expect(screen.getByTestId("add-project-button")).toBeDisabled();
  });
  it("creates a project of the default type when there is only one", () => {
    const onClick = jest.fn();
    render(
      <AddFolderButton
        {...defaultProps}
        onClick={onClick}
        projectTypes={[FLOWS]}
      />,
    );

    fireEvent.click(screen.getByTestId("add-project-button"));

    expect(onClick).toHaveBeenCalledWith();
  });

  it("offers every type once the server registers more than one", () => {
    render(
      <AddFolderButton {...defaultProps} projectTypes={[FLOWS, HARNESS]} />,
    );

    expect(screen.getByTestId("add-project-flows")).toBeInTheDocument();
    expect(screen.getByTestId("add-project-agent-harness")).toBeInTheDocument();
  });

  it("creates a project of the type that was picked", () => {
    const onClick = jest.fn();
    render(
      <AddFolderButton
        {...defaultProps}
        onClick={onClick}
        projectTypes={[FLOWS, HARNESS]}
      />,
    );

    fireEvent.click(screen.getByTestId("add-project-agent-harness"));

    expect(onClick).toHaveBeenCalledWith("agent-harness");
  });
});
