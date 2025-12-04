import { fireEvent, render, screen } from "@testing-library/react";
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

const mockStopBuilding = jest.fn();
const mockIsBuilding = jest.fn().mockReturnValue(false);

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (
    selector: (state: {
      stopBuilding: () => void;
      isBuilding: boolean;
    }) => unknown,
  ) =>
    selector({
      stopBuilding: mockStopBuilding,
      isBuilding: mockIsBuilding(),
    }),
}));

describe("ButtonSendWrapper", () => {
  const defaultProps = {
    send: jest.fn(),
    noInput: false,
    chatValue: "",
    files: [] as { loading?: boolean }[],
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockIsBuilding.mockReturnValue(false);
  });

  it("renders send button when not building", () => {
    render(<ButtonSendWrapper {...defaultProps} />);
    expect(screen.getByTestId("button-send")).toBeInTheDocument();
    expect(screen.getByTestId("icon-ArrowUp")).toBeInTheDocument();
  });

  it("renders stop button when building", () => {
    mockIsBuilding.mockReturnValue(true);
    render(<ButtonSendWrapper {...defaultProps} />);
    expect(screen.getByTestId("button-stop")).toBeInTheDocument();
    expect(screen.getByText("Stop")).toBeInTheDocument();
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("renders stop button when files are loading", () => {
    render(<ButtonSendWrapper {...defaultProps} files={[{ loading: true }]} />);
    expect(screen.getByTestId("button-stop")).toBeInTheDocument();
  });

  it("calls send when send button is clicked", () => {
    const send = jest.fn();
    render(<ButtonSendWrapper {...defaultProps} send={send} />);
    fireEvent.click(screen.getByTestId("button-send"));
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("calls stopBuilding when stop button is clicked while building", () => {
    mockIsBuilding.mockReturnValue(true);
    render(<ButtonSendWrapper {...defaultProps} />);
    fireEvent.click(screen.getByTestId("button-stop"));
    expect(mockStopBuilding).toHaveBeenCalledTimes(1);
  });

  it("does not render send icon when noInput is true and not building", () => {
    render(<ButtonSendWrapper {...defaultProps} noInput={true} />);
    // When noInput is true and not building, showSendButton is false
    expect(screen.queryByTestId("icon-ArrowUp")).not.toBeInTheDocument();
  });
});
