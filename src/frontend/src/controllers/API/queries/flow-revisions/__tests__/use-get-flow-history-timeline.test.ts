const getFlowRevisionsMock = jest.fn();
const getFlowRevisionMock = jest.fn();
jest.mock("../use-get-flow-revisions", () => ({
  MAX_PAGE_SIZE: 200,
  getFlowRevisions: (...args: unknown[]) => getFlowRevisionsMock(...args),
}));
jest.mock("../use-get-flow-revision", () => ({
  getFlowRevision: (...args: unknown[]) => getFlowRevisionMock(...args),
}));
jest.mock("../../../services/request-processor", () => ({
  UseRequestProcessor: () => ({ query: jest.fn() }),
}));

import { getFlowHistoryTimeline } from "../use-get-flow-history-timeline";

const node = (value: string) => ({
  id: "a",
  data: { node: { template: { text: { value } } } },
});
const graph = (value: string) => ({ nodes: [node(value)], edges: [] });
const setText = (revision: number, value: string) => ({
  revision,
  actor_user_id: "u",
  request_id: "r",
  operation: {
    type: "update_nodes",
    updates: [
      {
        id: "a",
        op: "set_field",
        path: ["data", "node", "template", "text", "value"],
        value,
      },
    ],
  },
});
const entry = (start: number, end: number, values: string[]) => ({
  start_revision: start,
  end_revision: end,
  created_at: "2026-10-19T00:00:00Z",
  actor_user_ids: ["u"],
  request_ids: ["r"],
  versions: [],
  operations: values.map((value, index) => setText(start + index, value)),
});

describe("getFlowHistoryTimeline", () => {
  beforeEach(() => jest.clearAllMocks());

  it("replays from the revision before the oldest entry", async () => {
    getFlowRevisionsMock.mockResolvedValueOnce({
      entries: [entry(2, 2, ["c"]), entry(1, 1, ["b"])],
      next_before: null,
    });
    getFlowRevisionMock.mockResolvedValueOnce({ data: graph("a") });

    const timeline = await getFlowHistoryTimeline("flow-1");

    expect(getFlowRevisionMock).toHaveBeenCalledWith("flow-1", 0);
    expect(timeline?.baseRevision).toBe(0);
    expect(timeline?.operations.map((operation) => operation.revision)).toEqual(
      [1, 2],
    );
  });

  it("replays only the entries after a gap left by history that was off", async () => {
    // Revision 3 is the checkpoint the history resumed from: no operation made it.
    getFlowRevisionsMock.mockResolvedValueOnce({
      entries: [entry(4, 5, ["e", "f"]), entry(1, 2, ["b", "c"])],
      next_before: null,
    });
    getFlowRevisionMock.mockResolvedValueOnce({ data: graph("d") });

    const timeline = await getFlowHistoryTimeline("flow-1");

    expect(getFlowRevisionMock).toHaveBeenCalledWith("flow-1", 3);
    expect(timeline?.baseRevision).toBe(3);
    expect(timeline?.entries.map((item) => item.start_revision)).toEqual([4]);
    expect(timeline?.operations.map((operation) => operation.revision)).toEqual(
      [4, 5],
    );
    expect(timeline?.cursor.graph).toEqual(graph("f"));
  });
});
