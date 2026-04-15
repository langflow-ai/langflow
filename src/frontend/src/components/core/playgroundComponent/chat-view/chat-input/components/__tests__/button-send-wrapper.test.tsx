import { fireEvent, render, screen } from "@testing-library/react";
import type { FilePreviewType } from "@/types/components";
import ButtonSendWrapper from "../button-send-wrapper";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <div data-testid={`icon-${name}`} className={className}>
      {name}
    </div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    className,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
    className?: string;
  } & Record<string, unknown>) => (
    <button onClick={onClick} className={className} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: ({ className }: { className?: string }) => (
    <div data-testid="loading" className={className} />
  ),
}));

jest.mock("@/shared/components/caseComponent", () => ({
  Case: ({
    condition,
    children,
  }: {
    condition: boolean;
    children: React.ReactNode;
  }) => (condition ? <>{children}</> : null),
}));

describe("ButtonSendWrapper", () => {
  const mockFile = new File(["test"], "test.txt", { type: "text/plain" });

  const createMockFilePreview = (loading: boolean): FilePreviewType => ({
    loading,
    file: mockFile,
    error: false,
    id: "test-id",
  });

  const defaultProps = {
    send: jest.fn(),
    noInput: false,
    chatValue: "",
    files: [] as FilePreviewType[],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders send button", () => {
    render(<ButtonSendWrapper {...defaultProps} />);
    expect(screen.getByTestId("button-send")).toBeInTheDocument();
    expect(screen.getByTestId("icon-ArrowUp")).toBeInTheDocument();
  });

  it("disables button when files are loading", () => {
    render(
      <ButtonSendWrapper
        {...defaultProps}
        files={[createMockFilePreview(true)]}
      />,
    );
    const button = screen.getByTestId("button-send");
    expect(button).toBeDisabled();
  });

  it("calls send when send button is clicked", () => {
    const send = jest.fn();
    render(<ButtonSendWrapper {...defaultProps} send={send} />);
    fireEvent.click(screen.getByTestId("button-send"));
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("does not call send when button is disabled (files loading)", () => {
    const send = jest.fn();
    render(
      <ButtonSendWrapper
        {...defaultProps}
        send={send}
        files={[createMockFilePreview(true)]}
      />,
    );
    fireEvent.click(screen.getByTestId("button-send"));
    expect(send).not.toHaveBeenCalled();
  });

  it("applies correct styling when noInput is true", () => {
    render(<ButtonSendWrapper {...defaultProps} noInput={true} />);
    const button = screen.getByTestId("button-send");
    expect(button.className).toContain("bg-high-indigo");
  });

  it("applies correct styling when noInput is false", () => {
    render(<ButtonSendWrapper {...defaultProps} noInput={false} />);
    const button = screen.getByTestId("button-send");
    expect(button.className).toContain("bg-primary");
  });
});
