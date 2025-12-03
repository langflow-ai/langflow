import { fireEvent, render, screen } from "@testing-library/react";
import AudioButton from "../audio-button";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <div data-testid={`icon-${name}`} className={className}>
      {name}
    </div>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content: string;
  }) => (
    <div data-testid="tooltip" data-content={content}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    className,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
    disabled?: boolean;
    className?: string;
  } & Record<string, unknown>) => (
    <button
      onClick={onClick}
      disabled={disabled}
      className={className}
      {...props}
    >
      {children}
    </button>
  ),
}));

describe("AudioButton", () => {
  const defaultProps = {
    isBuilding: false,
    recordingState: "idle" as const,
    onStartRecording: jest.fn(),
    onStopRecording: jest.fn(),
    isSupported: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders Mic icon when idle", () => {
    render(<AudioButton {...defaultProps} />);
    expect(screen.getByTestId("icon-Mic")).toBeInTheDocument();
  });

  it("renders MicOff icon when recording", () => {
    render(<AudioButton {...defaultProps} recordingState="recording" />);
    expect(screen.getByTestId("icon-MicOff")).toBeInTheDocument();
  });

  it("shows 'Voice input' tooltip when idle and supported", () => {
    render(<AudioButton {...defaultProps} />);
    expect(screen.getByTestId("tooltip")).toHaveAttribute(
      "data-content",
      "Voice input",
    );
  });

  it("shows 'Stop recording' tooltip when recording", () => {
    render(<AudioButton {...defaultProps} recordingState="recording" />);
    expect(screen.getByTestId("tooltip")).toHaveAttribute(
      "data-content",
      "Stop recording",
    );
  });

  it("shows 'Processing...' tooltip when processing", () => {
    render(<AudioButton {...defaultProps} recordingState="processing" />);
    expect(screen.getByTestId("tooltip")).toHaveAttribute(
      "data-content",
      "Processing...",
    );
  });

  it("shows unsupported message when not supported", () => {
    render(<AudioButton {...defaultProps} isSupported={false} />);
    expect(screen.getByTestId("tooltip")).toHaveAttribute(
      "data-content",
      "Voice input not supported in this browser",
    );
  });

  it("calls onStartRecording when clicked while idle", () => {
    const onStartRecording = jest.fn();
    render(
      <AudioButton {...defaultProps} onStartRecording={onStartRecording} />,
    );
    fireEvent.click(screen.getByTestId("audio-button"));
    expect(onStartRecording).toHaveBeenCalledTimes(1);
  });

  it("calls onStopRecording when clicked while recording", () => {
    const onStopRecording = jest.fn();
    render(
      <AudioButton
        {...defaultProps}
        recordingState="recording"
        onStopRecording={onStopRecording}
      />,
    );
    fireEvent.click(screen.getByTestId("audio-button"));
    expect(onStopRecording).toHaveBeenCalledTimes(1);
  });

  it("is disabled when isBuilding is true", () => {
    render(<AudioButton {...defaultProps} isBuilding={true} />);
    expect(screen.getByTestId("audio-button")).toBeDisabled();
  });

  it("is disabled when processing", () => {
    render(<AudioButton {...defaultProps} recordingState="processing" />);
    expect(screen.getByTestId("audio-button")).toBeDisabled();
  });

  it("is disabled when not supported", () => {
    render(<AudioButton {...defaultProps} isSupported={false} />);
    expect(screen.getByTestId("audio-button")).toBeDisabled();
  });

  it("applies destructive styling when recording", () => {
    render(<AudioButton {...defaultProps} recordingState="recording" />);
    const button = screen.getByTestId("audio-button");
    expect(button.className).toContain("text-destructive");
    expect(button.className).toContain("animate-pulse");
  });
});
