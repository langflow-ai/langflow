import { render, screen } from "@testing-library/react";
import SwitchOutputView from "../components/switchOutputView";

const mockRows = [
  { type: "human", data: { content: "Research this topic", type: "human" } },
];
let mockOutputTypes = ["Table"];

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      nodes: [
        {
          id: "context",
          data: {
            node: { outputs: [{ name: "messages", types: mockOutputTypes }] },
          },
        },
      ],
      flowPool: {
        context: [
          {
            data: {
              outputs: {
                messages: { type: "array", message: { raw: mockRows } },
              },
            },
          },
        ],
      },
    }),
}));

jest.mock("@/components/core/dataOutputComponent", () => ({
  __esModule: true,
  default: ({ rows }: { rows: unknown[] }) => (
    <pre data-testid="table-rows">{JSON.stringify(rows)}</pre>
  ),
}));

jest.mock("@/components/core/jsonOutputComponent/json-output-view", () => ({
  __esModule: true,
  default: () => null,
}));

it.each(["Table", "DataFrame"])(
  "preserves the data column and sibling columns of %s output",
  (outputType) => {
    mockOutputTypes = [outputType];
    render(
      <SwitchOutputView
        nodeId="context"
        outputName="messages"
        type="outputs"
      />,
    );
    expect(JSON.parse(screen.getByTestId("table-rows").textContent!)).toEqual(
      mockRows,
    );
  },
);

it("still unwraps legacy Data envelopes for non-table output", () => {
  mockOutputTypes = ["Data"];
  render(
    <SwitchOutputView nodeId="context" outputName="messages" type="outputs" />,
  );
  expect(JSON.parse(screen.getByTestId("table-rows").textContent!)).toEqual([
    mockRows[0].data,
  ]);
});
