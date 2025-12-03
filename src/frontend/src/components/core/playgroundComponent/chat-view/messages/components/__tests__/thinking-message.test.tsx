import { render, screen } from "@testing-library/react";
import ThinkingMessage from "../thinking-message";

// Mock the thinking duration store
jest.mock("../../hooks/use-thinking-duration", () => ({
  useThinkingDurationStore: Object.assign(
    () => ({
      startTime: Date.now(),
    }),
    {
      getState: () => ({
        startTime: Date.now(),
      }),
    },
  ),
}));

// Mock the icon component
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className: string }) => (
    <div data-testid={`icon-${name}`} className={className} />
  ),
}));

describe("ThinkingMessage Component", () => {
  it("renders thinking state correctly", () => {
    render(<ThinkingMessage isThinking={true} duration={null} />);

    expect(screen.getByTestId("icon-Brain")).toBeInTheDocument();
    expect(screen.getByText(/Thinking for/)).toBeInTheDocument();
  });

  it("renders thought state with duration", () => {
    render(<ThinkingMessage isThinking={false} duration={5000} />);

    expect(screen.getByTestId("icon-Brain")).toBeInTheDocument();
    expect(screen.getByText(/Thought for/)).toBeInTheDocument();
    expect(screen.getByText(/5.0s/)).toBeInTheDocument();
  });

  it("applies pulse animation when thinking", () => {
    render(<ThinkingMessage isThinking={true} duration={null} />);

    const icon = screen.getByTestId("icon-Brain");
    expect(icon.className).toContain("animate-pulse");
    expect(icon.className).toContain("text-primary");
  });

  it("applies muted color when not thinking", () => {
    render(<ThinkingMessage isThinking={false} duration={3000} />);

    const icon = screen.getByTestId("icon-Brain");
    expect(icon.className).toContain("text-muted-foreground");
    expect(icon.className).not.toContain("animate-pulse");
  });

  it("formats time in minutes when duration exceeds 60 seconds", () => {
    render(<ThinkingMessage isThinking={false} duration={90000} />);

    expect(screen.getByText(/1m 30s/)).toBeInTheDocument();
  });

  it("shows 0s when duration is null and not thinking", () => {
    render(<ThinkingMessage isThinking={false} duration={null} />);

    expect(screen.getByText(/Thought for/)).toBeInTheDocument();
    expect(screen.getByText(/0.0s/)).toBeInTheDocument();
  });
});
