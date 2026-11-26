import { render, screen } from "@testing-library/react";
import type { FlowType } from "@/types/flow";
import { HarnessSummary } from "../components/harness-summary";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: (string | boolean | undefined)[]) =>
    classes.filter(Boolean).join(" "),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span data-testid="badge">{children}</span>
  ),
}));

const flow = (id: string, name: string): FlowType =>
  ({ id, name, description: "" }) as FlowType;

const defaultProps = {
  displayName: "Agent Harness",
  icon: "Bot",
  toolFlows: [] as FlowType[],
  details: [] as { name: string; label: string; value: string }[],
};

describe("HarnessSummary", () => {
  it("names the type it is summarising", () => {
    render(<HarnessSummary {...defaultProps} />);

    expect(screen.getByText("Agent Harness")).toBeInTheDocument();
  });

  it("reads back the model the widget stored, provider and all", () => {
    render(
      <HarnessSummary
        {...defaultProps}
        model={[{ name: "gpt-4o", provider: "OpenAI" }]}
      />,
    );

    expect(screen.getByTestId("harness-summary-model")).toHaveTextContent(
      "gpt-4o · OpenAI",
    );
  });

  it("reads back a model stored as a bare string", () => {
    render(<HarnessSummary {...defaultProps} model="gpt-4o" />);

    expect(screen.getByTestId("harness-summary-model")).toHaveTextContent(
      "gpt-4o",
    );
  });

  it("says no model is picked rather than showing an empty line", () => {
    render(<HarnessSummary {...defaultProps} model={[]} />);

    expect(
      screen.getByTestId("harness-summary-model-empty"),
    ).toBeInTheDocument();
  });

  it("treats a model entry with no name as nothing picked", () => {
    render(
      <HarnessSummary {...defaultProps} model={[{ provider: "OpenAI" }]} />,
    );

    expect(
      screen.getByTestId("harness-summary-model-empty"),
    ).toBeInTheDocument();
  });

  it("lists the flows the agent can call", () => {
    render(
      <HarnessSummary
        {...defaultProps}
        toolFlows={[flow("f1", "Search docs"), flow("f2", "Send email")]}
      />,
    );

    expect(screen.getByTestId("harness-summary-tool-f1")).toHaveTextContent(
      "Search docs",
    );
    expect(screen.getByTestId("harness-summary-tool-f2")).toHaveTextContent(
      "Send email",
    );
  });

  it("counts the tools", () => {
    render(
      <HarnessSummary {...defaultProps} toolFlows={[flow("f1", "Search")]} />,
    );

    expect(screen.getByTestId("badge")).toHaveTextContent("1");
  });

  it("says no flows are picked rather than showing an empty list", () => {
    render(<HarnessSummary {...defaultProps} />);

    expect(
      screen.getByTestId("harness-summary-tools-empty"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("badge")).not.toBeInTheDocument();
  });

  it("shows the remaining fields as rows", () => {
    render(
      <HarnessSummary
        {...defaultProps}
        details={[{ name: "n_messages", label: "Memory", value: "100" }]}
      />,
    );

    expect(
      screen.getByTestId("harness-summary-detail-n_messages"),
    ).toHaveTextContent("100");
    expect(screen.getByText("Memory")).toBeInTheDocument();
  });
});
