import i18n from "@/i18n";
import type { RecordedOperation } from "@/types/flow/revision";
import {
  describeOperation,
  fieldLabelsFrom,
  summarizeOperations,
} from "../describe";

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
    ).toEqual(["Edited Temperature, Model on OpenAI", "Moved Prompt"]);
    expect(
      describeOperation(
        recorded(
          { type: "update_nodes", updates: [field("seed", "7", "number")] },
          labels,
        ),
        t,
      ),
    ).toEqual(["Changed Seed on OpenAI from number to string"]);
  });

  it("uses a field's label from the flow when it has one", () => {
    const fieldLabel = fieldLabelsFrom({
      nodes: [
        {
          id: "a",
          data: {
            node: { template: { api_key: { display_name: "API Key" } } },
          },
        },
      ],
    });
    const edit = (id: string, name: string) =>
      recorded(
        {
          type: "update_nodes",
          updates: [
            {
              id,
              op: "set_field",
              path: ["data", "node", "template", name, "value"],
              value: "x",
            },
          ],
        },
        labels,
      );

    expect(describeOperation(edit("a", "api_key"), t, { fieldLabel })).toEqual([
      "Edited API Key on OpenAI",
    ]);
    // A node the flow no longer has falls back to the humanized key.
    expect(
      describeOperation(edit("b", "sender_name"), t, { fieldLabel }),
    ).toEqual(["Edited Sender name on Prompt"]);
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
