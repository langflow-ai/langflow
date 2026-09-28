import i18n from "@/i18n";
import type { RecordedOperation } from "@/types/flow/revision";
import { describeOperation, summarizeOperations } from "../describe";

const t = (key: string, opts?: object) => i18n.t(key, opts) as string;

function recorded(
  operation: RecordedOperation["operation"],
  labels: RecordedOperation["labels"] = {},
): RecordedOperation {
  return {
    revision: 1,
    actor: { id: "u1", username: "alice" },
    request_id: "r1",
    operation,
    labels,
  };
}

const labels = { nodes: { a: "OpenAI", b: "Prompt" } };

describe("describeOperation", () => {
  it("names added and deleted nodes by their recorded display names", () => {
    expect(
      describeOperation(
        recorded({ type: "add_nodes", nodes: [{ id: "a" }] }, labels),
        t,
      ),
    ).toEqual(["Added OpenAI"]);
    expect(
      describeOperation(
        recorded({ type: "delete_nodes", ids: ["a", "b"] }, labels),
        t,
      ),
    ).toEqual(["Deleted 2 components"]);
  });

  it("describes connections from both ends", () => {
    expect(
      describeOperation(
        recorded(
          { type: "add_edges", edges: [{ id: "e", source: "b", target: "a" }] },
          labels,
        ),
        t,
      ),
    ).toEqual(["Connected Prompt → OpenAI"]);
    expect(
      describeOperation(
        recorded(
          { type: "delete_edges", ids: ["e"] },
          { ...labels, edges: { e: { source: "b", target: "a" } } },
        ),
        t,
      ),
    ).toEqual(["Disconnected Prompt → OpenAI"]);
  });

  it("names edited fields, moves, and type changes per node", () => {
    const field = (name: string, value: unknown, from_type?: string) => ({
      id: "a",
      op: "set_field",
      path: ["data", "node", "template", name, "value"],
      value,
      ...(from_type && { from_type }),
    });
    expect(
      describeOperation(
        recorded(
          {
            type: "update_nodes",
            updates: [
              field("temperature", 0.2),
              field("model", "gpt"),
              {
                id: "b",
                op: "set_field",
                path: ["position"],
                value: { x: 1, y: 2 },
              },
            ],
          },
          labels,
        ),
        t,
      ),
    ).toEqual(["Edited temperature, model on OpenAI", "Moved Prompt"]);
    expect(
      describeOperation(
        recorded(
          { type: "update_nodes", updates: [field("seed", "7", "number")] },
          labels,
        ),
        t,
      ),
    ).toEqual(["Changed seed on OpenAI from number to string"]);
  });

  it("falls back to the node id when no name was recorded", () => {
    expect(
      describeOperation(
        recorded({ type: "add_nodes", nodes: [{ id: "x" }] }),
        t,
      ),
    ).toEqual(["Added x"]);
  });
});

describe("summarizeOperations", () => {
  it("shows the first two changes and counts the rest", () => {
    const operations = ["a", "b", "a"].map((id) =>
      recorded({ type: "add_nodes", nodes: [{ id }] }, labels),
    );

    expect(summarizeOperations(operations, t)).toBe(
      "Added OpenAI; Added Prompt and 1 more change",
    );
  });
});
