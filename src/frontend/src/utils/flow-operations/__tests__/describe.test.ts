import i18n from "@/i18n";
import type { RecordedOperation } from "@/types/flow/revision";
import {
  describeOperation,
  fieldLabelsFrom,
  summarizeOperations,
} from "../describe";
import { collectHistoryNames, flowNames } from "../names";

const t = (key: string, opts?: object) => i18n.t(key, opts) as string;

function recorded(
  operation: RecordedOperation["operation"],
): RecordedOperation {
  return {
    revision: 1,
    actor: { id: "u1", username: "alice" },
    request_id: "r1",
    operation,
  };
}

const named = (id: string, name: string) => ({
  id,
  data: { node: { display_name: name, template: {} } },
});
// "a" is in the flow now; "b" was deleted, so only its history names it.
const names = flowNames(
  { nodes: [named("a", "OpenAI")] },
  collectHistoryNames({ nodes: [named("b", "Prompt")], edges: [] }, [
    recorded({
      type: "add_edges",
      edges: [{ id: "e", source: "b", target: "a" }],
    }),
  ]),
);

describe("describeOperation", () => {
  it("names nodes from the flow, then from the history", () => {
    expect(
      describeOperation(
        recorded({ type: "add_nodes", nodes: [{ id: "a" }] }),
        t,
        { names },
      ),
    ).toEqual(["Added OpenAI"]);
    expect(
      describeOperation(
        recorded({ type: "delete_nodes", ids: ["a", "b"] }),
        t,
        { names },
      ),
    ).toEqual(["Deleted 2 components"]);
  });

  it("describes connections from both ends", () => {
    expect(
      describeOperation(
        recorded({
          type: "add_edges",
          edges: [{ id: "e", source: "b", target: "a" }],
        }),
        t,
        { names },
      ),
    ).toEqual(["Connected Prompt → OpenAI"]);
    expect(
      describeOperation(recorded({ type: "delete_edges", ids: ["e"] }), t, {
        names,
      }),
    ).toEqual(["Disconnected Prompt → OpenAI"]);
    expect(
      describeOperation(
        recorded({ type: "delete_edges", ids: ["unseen"] }),
        t,
        { names },
      ),
    ).toEqual(["Removed a connection"]);
  });

  it("describes a connection's own changes", () => {
    const update = (id: string) => ({
      id,
      op: "set_field",
      path: ["data", "targetHandle", "inputTypes"],
      value: ["Data"],
    });
    expect(
      describeOperation(
        recorded({ type: "update_edges", updates: [update("e"), update("x")] }),
        t,
        { names },
      ),
    ).toEqual(["Updated connection Prompt → OpenAI", "Updated a connection"]);
  });

  it("describes table rows, cells and outputs addressed by selectors", () => {
    const rows = ["data", "node", "template", "headers", "value"];
    const outputs = ["data", "node", "outputs"];
    expect(
      describeOperation(
        recorded({
          type: "update_nodes",
          updates: [
            {
              id: "a",
              op: "set_field",
              path: [...rows, { id: "r1" }, "v"],
              value: "x",
            },
            {
              id: "a",
              op: "set_field",
              path: [...rows, { id: "r2" }],
              value: { _id: "r2" },
            },
            {
              id: "a",
              op: "set_field",
              path: [...rows, { id: "r3" }],
              value: { _id: "r3" },
            },
            { id: "a", op: "delete_field", path: [...rows, { id: "r4" }] },
            {
              id: "a",
              op: "set_field",
              path: [...rows, { id: "r5" }, "_pos"],
              value: "a3",
            },
            {
              id: "a",
              op: "set_field",
              path: [...outputs, { key: "text_output" }, "hidden"],
              value: true,
            },
            {
              id: "a",
              op: "set_field",
              path: [...outputs, { key: "model" }, "hidden"],
              value: false,
            },
          ],
        }),
        t,
        { names },
      ),
    ).toEqual([
      "Edited Headers on OpenAI",
      "Added 2 rows to Headers on OpenAI",
      "Removed a row from Headers on OpenAI",
      "Moved a row in Headers on OpenAI",
      "Hid output Text output on OpenAI",
      "Showed output Model on OpenAI",
    ]);
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
        recorded({
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
        }),
        t,
        { names },
      ),
    ).toEqual(["Edited Temperature, Model on OpenAI", "Moved Prompt"]);
    expect(
      describeOperation(
        recorded({
          type: "update_nodes",
          updates: [field("seed", "7", "number")],
        }),
        t,
        { names },
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
      recorded({
        type: "update_nodes",
        updates: [
          {
            id,
            op: "set_field",
            path: ["data", "node", "template", name, "value"],
            value: "x",
          },
        ],
      });

    expect(
      describeOperation(edit("a", "api_key"), t, { fieldLabel, names }),
    ).toEqual(["Edited API Key on OpenAI"]);
    // A node the flow no longer has falls back to the humanized key.
    expect(
      describeOperation(edit("b", "sender_name"), t, { fieldLabel, names }),
    ).toEqual(["Edited Sender name on Prompt"]);
  });

  it("falls back to the node id when no name is known", () => {
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
      recorded({ type: "add_nodes", nodes: [{ id }] }),
    );

    expect(summarizeOperations(operations, t, { names })).toBe(
      "Added OpenAI; Added Prompt and 1 more change",
    );
  });
});
