import { render, screen } from "@testing-library/react";
import { SpanDetail } from "../SpanDetail";
import type { Span } from "../types";

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
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

const buildSpan = (overrides: Partial<Span> = {}): Span => ({
  id: "span-1",
  name: "Test Span",
  type: "llm",
  status: "ok",
  startTime: "2024-01-01T00:00:00Z",
  endTime: "2024-01-01T00:00:01Z",
  latencyMs: 1200,
  inputs: { foo: "bar" },
  outputs: { result: "ok" },
  error: undefined,
  modelName: "gpt-test",
  tokenUsage: {
    promptTokens: 10,
    completionTokens: 20,
    totalTokens: 30,
    cost: 0.5,
  },
  children: [],
  ...overrides,
});

describe("SpanDetail", () => {
  it("renders empty state when no span selected", () => {
    render(<SpanDetail span={null} />);

    expect(screen.getByTestId("span-detail-empty")).toBeInTheDocument();
    expect(
      screen.getByText("Select a span to view details"),
    ).toBeInTheDocument();
  });

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

  it("renders error message when span has error", () => {
    render(<SpanDetail span={buildSpan({ error: "Something broke" })} />);

    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("Something broke")).toBeInTheDocument();
  });

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

  it("displays latency metric", () => {
    render(<SpanDetail span={buildSpan()} />);

    expect(screen.getByText("Latency")).toBeInTheDocument();
  });

  it("displays model name when available", () => {
    render(<SpanDetail span={buildSpan({ modelName: "gpt-4" })} />);

    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  it("does not display model name separator when model is undefined", () => {
    render(<SpanDetail span={buildSpan({ modelName: undefined })} />);

    const separators = screen.queryAllByText("|");
    expect(separators.length).toBe(0);
  });

  it("displays only inputs when outputs are empty", () => {
    render(<SpanDetail span={buildSpan({ outputs: {} })} />);

    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(screen.queryByText("Output")).not.toBeInTheDocument();
  });

  it("displays only outputs when inputs are empty", () => {
    render(<SpanDetail span={buildSpan({ inputs: {} })} />);

    expect(screen.queryByText("Input")).not.toBeInTheDocument();
    expect(screen.getByText("Output")).toBeInTheDocument();
  });

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
