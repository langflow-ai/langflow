import { render, screen } from "@testing-library/react";
import type { RunEstimate } from "@/controllers/API/queries/evals/types";
import { axe } from "@/utils/a11y-test";
import EstimateCard from "../EstimateCard";
import EvaluationPreflight from "../EvaluationPreflight";

const REPORT = {
  blocking: [
    { code: "human_in_the_loop", message: "server text", components: [] },
  ],
  warnings: [
    {
      code: "external_actions",
      message: "server text",
      components: ["Send Email"],
    },
  ],
  output_vertices: [{ id: "ChatOutput-1", name: "Chat Output" }],
};

const ESTIMATE: RunEstimate = {
  items: 10,
  basis: "model",
  llm_calls: 20,
  judge_calls: 10,
  flow_tokens_low: 1000,
  flow_tokens_high: 3000,
  judge_tokens_low: 2000,
  judge_tokens_high: 5000,
  tokens_low: 3000,
  tokens_high: 8000,
  cost_low: 0.001,
  cost_high: 0.004,
  unpriced_models: [],
  has_agent: false,
};

describe("EvaluationPreflight", () => {
  it("should translate issues by code and name the risky components", () => {
    render(<EvaluationPreflight report={REPORT} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The flow pauses for human approval",
    );
    expect(screen.getByTestId("evaluate-warnings")).toHaveTextContent(
      "(Send Email)",
    );
  });

  it("should render nothing for a clean flow", () => {
    const { container } = render(
      <EvaluationPreflight
        report={{ blocking: [], warnings: [], output_vertices: [] }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("should have no accessibility violations", async () => {
    const { container } = render(<EvaluationPreflight report={REPORT} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("EstimateCard", () => {
  it("should show the token and cost range with the flow and judge breakdown", () => {
    render(<EstimateCard estimate={ESTIMATE} loading={false} />);
    const card = screen.getByTestId("evaluate-estimate");
    expect(card).toHaveTextContent("3,000 – 8,000");
    expect(card).toHaveTextContent("Rough estimate");
    expect(card).toHaveTextContent("10 calls");
  });

  it("should say a run without model calls is free", () => {
    render(
      <EstimateCard
        estimate={{ ...ESTIMATE, llm_calls: 0, judge_calls: 0 }}
        loading={false}
      />,
    );
    expect(screen.getByTestId("evaluate-estimate")).toHaveTextContent(
      "No model calls",
    );
  });

  it("should name models without a known price instead of guessing", () => {
    render(
      <EstimateCard
        estimate={{
          ...ESTIMATE,
          cost_low: null,
          cost_high: null,
          unpriced_models: ["mystery"],
        }}
        loading={false}
      />,
    );
    expect(screen.getByTestId("evaluate-estimate")).toHaveTextContent(
      "mystery",
    );
  });

  it("should have no accessibility violations", async () => {
    const { container } = render(
      <EstimateCard estimate={ESTIMATE} loading={false} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
