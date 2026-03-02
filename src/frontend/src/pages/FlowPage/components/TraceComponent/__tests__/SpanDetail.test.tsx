import { render, screen } from "@testing-library/react";
import { type ReactNode } from "react";
import { SpanDetail } from "../SpanDetail";
import { buildSpan } from "./spanTestUtils";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, ...props }: { name: string }) => (
    <span data-testid={`icon-${name}`} {...props} />
  ),
}));

jest.mock("@/components/core/codeTabsComponent", () => ({
  __esModule: true,
  default: ({ code }: { code: string }) => (
    <pre data-testid="code-tab">{code}</pre>
  ),
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

describe("SpanDetail", () => {
  // Verifies that when no span is selected (null), the empty-state placeholder is shown with the prompt text.
  it("renders empty state when no span selected", () => {
    render(<SpanDetail span={null} />);

    expect(screen.getByTestId("span-detail-empty")).toBeInTheDocument();
    expect(
      screen.getByText("Select a span to view details"),
    ).toBeInTheDocument();
  });

  // Verifies that a fully-populated span renders its name, type, model, token counts, cost, and I/O code blocks.
  it("renders span details with inputs, outputs, tokens, and cost", () => {
    render(<SpanDetail span={buildSpan()} />);

    expect(screen.getByTestId("span-detail")).toBeInTheDocument();
    expect(screen.getByText("Test Span")).toBeInTheDocument();
    expect(screen.getByText("LLM")).toBeInTheDocument();
    expect(screen.getByText("gpt-test")).toBeInTheDocument();
    expect(screen.getByText("Tokens")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("Prompt")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("Completion")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("Estimated Cost")).toBeInTheDocument();
    expect(screen.getByText("$0.5000")).toBeInTheDocument();

    const codeBlocks = screen.getAllByTestId("code-tab");
    expect(codeBlocks[0]).toHaveTextContent('"foo": "bar"');
    expect(codeBlocks[1]).toHaveTextContent('"result": "ok"');
  });

  // Verifies that when a span has an error string, the "Error" label and the error message are both displayed.
  it("renders error message when span has error", () => {
    render(<SpanDetail span={buildSpan({ error: "Something broke" })} />);

    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("Something broke")).toBeInTheDocument();
  });

  // Verifies that a span with empty inputs, outputs, no token usage, and no error shows the "No additional details" fallback.
  it("shows empty details when no inputs, outputs, or error", () => {
    render(
      <SpanDetail
        span={buildSpan({
          type: "tool",
          inputs: {},
          outputs: {},
          tokenUsage: undefined,
          error: undefined,
        })}
      />,
    );

    expect(
      screen.getByText("No additional details available"),
    ).toBeInTheDocument();
  });

  // Verifies that an LLM span missing token usage still renders the "Tokens" section with em-dash placeholders.
  it("renders token placeholders for LLM spans without token usage", () => {
    render(
      <SpanDetail
        span={buildSpan({
          tokenUsage: undefined,
          inputs: {},
          outputs: {},
        })}
      />,
    );

    expect(screen.getByText("Tokens")).toBeInTheDocument();
    expect(screen.getAllByText("\u2014").length).toBeGreaterThan(0);
  });

  // Verifies that non-LLM spans (e.g., tool) without token usage do not render the token section at all.
  it("does not show token section for non-LLM spans without token usage", () => {
    render(
      <SpanDetail
        span={buildSpan({
          type: "tool",
          tokenUsage: undefined,
          inputs: {},
          outputs: {},
        })}
      />,
    );

    expect(screen.queryByText("Tokens")).not.toBeInTheDocument();
    expect(
      screen.getByText("No additional details available"),
    ).toBeInTheDocument();
  });

  // Verifies that the "Latency" label is present in the rendered span detail header.
  it("displays latency metric", () => {
    render(<SpanDetail span={buildSpan()} />);

    expect(screen.getByText("Latency")).toBeInTheDocument();
  });

  // Verifies that when a modelName is set on the span, it appears in the rendered output.
  it("displays model name when available", () => {
    render(<SpanDetail span={buildSpan({ modelName: "gpt-4" })} />);

    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  // Verifies that when modelName is undefined, no "|" separator is rendered in the header.
  it("does not display model name separator when model is undefined", () => {
    render(<SpanDetail span={buildSpan({ modelName: undefined })} />);

    const separators = screen.queryAllByText("|");
    expect(separators.length).toBe(0);
  });

  // Verifies that when outputs are empty, only the "Input" section is shown and "Output" is absent.
  it("displays only inputs when outputs are empty", () => {
    render(<SpanDetail span={buildSpan({ outputs: {} })} />);

    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(screen.queryByText("Output")).not.toBeInTheDocument();
  });

  // Verifies that when inputs are empty, only the "Output" section is shown and "Input" is absent.
  it("displays only outputs when inputs are empty", () => {
    render(<SpanDetail span={buildSpan({ inputs: {} })} />);

    expect(screen.queryByText("Input")).not.toBeInTheDocument();
    expect(screen.getByText("Output")).toBeInTheDocument();
  });

  // Verifies that when token cost is exactly 0, the "Estimated Cost" row is not rendered.
  it("does not display cost when cost is zero", () => {
    render(
      <SpanDetail
        span={buildSpan({
          tokenUsage: {
            promptTokens: 10,
            completionTokens: 20,
            totalTokens: 30,
            cost: 0,
          },
        })}
      />,
    );

    expect(screen.queryByText("Estimated Cost")).not.toBeInTheDocument();
  });

  // Verifies that a span with status "error" renders the error status badge text in the header.
  it("renders span with error status badge", () => {
    render(
      <SpanDetail
        span={buildSpan({
          status: "error",
          error: "Test error",
        })}
      />,
    );

    expect(screen.getByText("error")).toBeInTheDocument();
  });
});
