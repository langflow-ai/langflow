import { render, screen } from "@testing-library/react";
import {
  acceptedChoice,
  transportStopped,
} from "@/components/core/decisionInspection/__tests__/decision-fixtures";
import SwitchOutputView from "../index";

// The JSON viewer and error view drag in editors unrelated to the decision panel.
jest.mock("@/components/core/jsonOutputComponent/json-output-view", () => ({
  __esModule: true,
  default: () => <div data-testid="json-output-view" />,
}));
jest.mock("../components", () => ({
  __esModule: true,
  default: ({ value }: { value: string }) => (
    <pre data-testid="error-output">{value}</pre>
  ),
}));

let mockFlowPool: Record<string, unknown[]> = {};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ flowPool: mockFlowPool, nodes: [] }),
}));

const renderOutput = (outputName = "category_5_result", type = "outputs") =>
  render(
    <SwitchOutputView
      nodeId="SmartRouter-1"
      outputName={outputName}
      type={type as "outputs" | "logs"}
    />,
  );

describe("SwitchOutputView decision evidence", () => {
  it("shows the decision above the raw JSON of a Smart Router output", () => {
    mockFlowPool = {
      "SmartRouter-1": [
        {
          data: {
            outputs: {
              category_5_result: {
                type: "object",
                message: { message: "hi", decision: acceptedChoice },
              },
            },
            logs: {},
          },
        },
      ],
    };

    renderOutput();

    const panel = screen.getByTestId("decision-inspection");
    expect(panel).toHaveTextContent("Branch: Billing");
    expect(
      panel.compareDocumentPosition(screen.getByTestId("json-output-view")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("falls back to the evidence log when the run stopped with an error", () => {
    mockFlowPool = {
      "SmartRouter-1": [
        {
          data: {
            outputs: {
              category_5_result: {
                type: "error",
                message: { errorMessage: "Langflow couldn't reach OpenAI." },
              },
            },
            logs: {
              category_5_result: [
                { name: "Decision evidence", message: transportStopped },
              ],
            },
          },
        },
      ],
    };

    renderOutput();

    expect(screen.getByTestId("decision-failure")).toHaveTextContent(
      "Connection failed",
    );
    expect(screen.getByTestId("error-output")).toBeInTheDocument();
  });

  it("shows no decision on the Logs tab or for other components", () => {
    mockFlowPool = {
      "SmartRouter-1": [
        {
          data: {
            outputs: { text: { type: "text", message: "plain" } },
            logs: {
              text: [{ name: "Decision evidence", message: acceptedChoice }],
            },
          },
        },
      ],
    };

    const { unmount } = renderOutput("text", "logs");
    expect(screen.queryByTestId("decision-inspection")).not.toBeInTheDocument();
    unmount();

    mockFlowPool = {
      "SmartRouter-1": [
        { data: { outputs: { text: { type: "text", message: "plain" } } } },
      ],
    };
    renderOutput("text");
    expect(screen.queryByTestId("decision-inspection")).not.toBeInTheDocument();
  });
});
