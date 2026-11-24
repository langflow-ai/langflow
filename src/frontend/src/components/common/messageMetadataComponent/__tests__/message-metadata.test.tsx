import { render, screen } from "@testing-library/react";
import MessageMetadata from "../index";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content: React.ReactNode;
  }) => (
    <div data-testid="tooltip-wrapper">
      <div data-testid="tooltip-content">{content}</div>
      <div data-testid="tooltip-trigger">{children}</div>
    </div>
  ),
}));

jest.mock("@/utils/format-token-count", () => ({
  formatTokenCount: (count: number | null | undefined) => {
    if (count == null || count <= 0) return null;
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
    return count.toString();
  },
}));

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format",
  () => ({
    formatSeconds: (ms: number) => `${(ms / 1000).toFixed(1)}s`,
  }),
);

describe("MessageMetadata", () => {
  // --- Happy path ---

  it("should_render_tokens_and_duration_when_both_provided", () => {
    render(
      <MessageMetadata
        duration={1800}
        usage={{ total_tokens: 49, input_tokens: 33, output_tokens: 16 }}
        timestamp="2026-04-06T19:07:32+00:00"
      />,
    );

    expect(screen.getByText("49")).toBeInTheDocument();
    // Duration appears in both tooltip and inline badge
    expect(screen.getAllByText("1.8s")).toHaveLength(2);
    expect(screen.getByText("|")).toBeInTheDocument();
  });

  it("should_render_only_tokens_when_no_duration", () => {
    render(
      <MessageMetadata
        duration={0}
        usage={{ total_tokens: 151, input_tokens: 37, output_tokens: 114 }}
      />,
    );

    expect(screen.getByText("151")).toBeInTheDocument();
    expect(screen.queryByText("|")).not.toBeInTheDocument();
  });

  it("should_render_only_duration_when_no_tokens", () => {
    render(<MessageMetadata duration={2500} usage={undefined} />);

    // Duration appears in both tooltip and inline badge
    expect(screen.getAllByText("2.5s")).toHaveLength(2);
    expect(screen.queryByText("|")).not.toBeInTheDocument();
    expect(screen.queryByTestId("icon-Coins")).not.toBeInTheDocument();
  });

  it("should_show_tooltip_with_input_and_output_tokens", () => {
    render(
      <MessageMetadata
        duration={1800}
        usage={{ total_tokens: 49, input_tokens: 33, output_tokens: 16 }}
        timestamp="2026-04-06T19:07:32+00:00"
      />,
    );

    const tooltipContent = screen.getByTestId("tooltip-content");
    expect(tooltipContent).toHaveTextContent("Last run:");
    expect(tooltipContent).toHaveTextContent("2026-04-06T19:07:32+00:00");
    expect(tooltipContent).toHaveTextContent("Duration:");
    expect(tooltipContent).toHaveTextContent("Input:");
    expect(tooltipContent).toHaveTextContent("33");
    expect(tooltipContent).toHaveTextContent("Output:");
    expect(tooltipContent).toHaveTextContent("16");
  });

  // --- Null / empty / boundary cases ---

  it("should_return_null_when_no_duration_and_no_tokens", () => {
    const { container } = render(
      <MessageMetadata duration={0} usage={undefined} />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("should_return_null_when_all_values_are_undefined", () => {
    const { container } = render(<MessageMetadata />);

    expect(container.firstChild).toBeNull();
  });

  it("should_return_null_when_tokens_are_zero", () => {
    const { container } = render(
      <MessageMetadata
        duration={0}
        usage={{ total_tokens: 0, input_tokens: 0, output_tokens: 0 }}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("should_return_null_when_tokens_are_null", () => {
    const { container } = render(
      <MessageMetadata
        duration={0}
        usage={{ total_tokens: null, input_tokens: null, output_tokens: null }}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("should_handle_negative_duration_as_no_duration", () => {
    const { container } = render(
      <MessageMetadata duration={-100} usage={undefined} />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("should_omit_timestamp_line_when_not_provided", () => {
    render(<MessageMetadata duration={1000} usage={{ total_tokens: 10 }} />);

    const tooltipContent = screen.getByTestId("tooltip-content");
    expect(tooltipContent).not.toHaveTextContent("Last run:");
  });

  it("should_format_large_token_counts", () => {
    render(
      <MessageMetadata
        duration={5000}
        usage={{ total_tokens: 1500, input_tokens: 500, output_tokens: 1000 }}
      />,
    );

    expect(screen.getByText("1.5K")).toBeInTheDocument();
  });

  it("should_omit_input_tokens_line_when_null", () => {
    render(
      <MessageMetadata
        duration={1000}
        usage={{ total_tokens: 50, input_tokens: null, output_tokens: 50 }}
      />,
    );

    const tooltipContent = screen.getByTestId("tooltip-content");
    expect(tooltipContent).not.toHaveTextContent("Input:");
    expect(tooltipContent).toHaveTextContent("Output:");
  });
});
