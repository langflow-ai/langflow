import type { FlowType } from "@/types/flow";

const mockCustomDownloadFlow = jest.fn();
const mockCustomDownloadNodeJson = jest.fn();

jest.mock("@/customization/utils/custom-reactFlowUtils", () => ({
  customDownloadFlow: (...args: unknown[]) => mockCustomDownloadFlow(...args),
}));

jest.mock("@/customization/utils/custom-download-json", () => ({
  customDownloadNodeJson: (...args: unknown[]) =>
    mockCustomDownloadNodeJson(...args),
}));

import { downloadFlow, downloadNode } from "../reactflowUtils";

const flowWithTable = (rows: Record<string, unknown>[]) =>
  ({
    id: "flow-1",
    name: "Flow",
    description: "",
    data: {
      nodes: [
        {
          id: "API-1",
          type: "genericNode",
          position: { x: 0, y: 0 },
          data: {
            id: "API-1",
            type: "APIRequest",
            node: {
              template: { headers: { type: "table", value: rows } },
            },
          },
        },
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  }) as unknown as FlowType;

describe("exports", () => {
  it("export flows without the editor's row ids and positions", async () => {
    const rows = [{ _id: "r1", _pos: "a0", key: "Accept", value: "json" }];

    await downloadFlow(flowWithTable(rows), "Flow", "");

    const exported = JSON.parse(mockCustomDownloadFlow.mock.calls[0][1]);
    expect(exported.data.nodes[0].data.node.template.headers.value).toEqual([
      { key: "Accept", value: "json" },
    ]);
    // The editor's own copy keeps them.
    expect(rows[0]._id).toBe("r1");
  });

  it("export components without the editor's row ids and positions", async () => {
    const rows = [{ _id: "r1", _pos: "a0", key: "Accept", value: "json" }];

    await downloadNode(flowWithTable(rows));

    const [exported] = mockCustomDownloadNodeJson.mock.calls[0];
    expect(exported.data.nodes[0].data.node.template.headers.value).toEqual([
      { key: "Accept", value: "json" },
    ]);
    expect(rows[0]._pos).toBe("a0");
  });
});
