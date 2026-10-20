import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
import { flowNames } from "@/utils/flow-operations/names";
import {
  countChanges,
  describeChanges,
  foldedCause,
  foldedSummary,
  summarizeEntry,
} from "../fold";

const en: Record<string, string> = {
  "flowHistory.unknownAuthor": "Unknown user",
  "flowHistory.fold.line": "{{action}}; {{changes}}",
  "flowHistory.fold.upgrade_component": "{{author}} updated {{name}}",
  "flowHistory.fold.edit_code": "{{author}} edited the code of {{name}}",
  "flowHistory.fold.restore": "{{author}} restored an earlier version",
  "flowHistory.fold.components_other": "{{count}} components",
  "flowHistory.fold.fieldsChanged_one": "{{count}} field changed",
  "flowHistory.fold.fieldsChanged_other": "{{count}} fields changed",
  "flowHistory.changes_other": "{{count}} changes",
  "flowHistory.op.editedFields": "Edited {{fields}} on {{name}}",
  "flowHistory.op.addedNode": "Added {{name}}",
  "flowHistory.op.noChanges": "No changes",
};

const t = (key: string, opts?: object) => {
  const params = (opts ?? {}) as Record<string, unknown>;
  const plural =
    typeof params.count === "number"
      ? `${key}_${params.count === 1 ? "one" : "other"}`
      : key;
  const template = en[plural] ?? en[key] ?? key;
  return template.replace(/\{\{(\w+)\}\}/g, (_, name) => String(params[name]));
};

const actor = { id: "u1", username: "Alice" };

const fieldWrites = (
  id: string,
  fields: string[],
  cause?: string,
): RecordedOperation => ({
  revision: 1,
  actor,
  request_id: "r",
  cause,
  operation: {
    type: "update_nodes",
    updates: fields.flatMap((field) => [
      {
        op: "set_field",
        id,
        path: ["data", "node", "template", field, "value"],
        value: 1,
      },
      {
        op: "set_field",
        id,
        path: ["data", "node", "template", field, "load_from_db"],
        value: false,
      },
    ]),
  },
});

// The flow as it is now names the components.
const names = flowNames({
  nodes: [
    { id: "A", data: { node: { display_name: "Agent" } } },
    { id: "B", data: { node: { display_name: "Prompt" } } },
  ],
});

const entry = (operations: RecordedOperation[]): RevisionEntry => ({
  id: "e1",
  start_revision: 1,
  end_revision: operations.length,
  created_at: null,
  actors: [actor],
  request_ids: ["r"],
  versions: [],
  operations,
});

describe("foldedCause", () => {
  it("is the cause every operation shares", () => {
    expect(
      foldedCause([
        fieldWrites("A", ["x"], "upgrade_component"),
        fieldWrites("A", ["y"], "upgrade_component"),
      ]),
    ).toBe("upgrade_component");
  });

  it("is null for mixed causes, no cause, or an unknown cause", () => {
    expect(
      foldedCause([
        fieldWrites("A", ["x"], "upgrade_component"),
        fieldWrites("A", ["y"]),
      ]),
    ).toBeNull();
    expect(foldedCause([fieldWrites("A", ["x"])])).toBeNull();
    expect(foldedCause([fieldWrites("A", ["x"], "something")])).toBeNull();
    expect(foldedCause([])).toBeNull();
    expect(foldedCause(null)).toBeNull();
  });
});

describe("countChanges", () => {
  it("counts a field's value, flags and definition as one changed field", () => {
    expect(
      countChanges([fieldWrites("A", ["x", "y"]), fieldWrites("B", ["x"])]),
    ).toEqual({ count: 3, onlyFields: true });
  });

  it("counts added components and connections one each", () => {
    const added: RecordedOperation = {
      ...fieldWrites("A", []),
      operation: { type: "add_nodes", nodes: [{ id: "N" }, { id: "M" }] },
    };
    expect(countChanges([fieldWrites("A", ["x"]), added])).toEqual({
      count: 3,
      onlyFields: false,
    });
  });
});

describe("foldedSummary", () => {
  it("reads as the action, with how many fields it changed", () => {
    const fields = Array.from({ length: 42 }, (_, i) => `f${i}`);
    expect(
      foldedSummary(entry([fieldWrites("A", fields, "upgrade_component")]), t, {
        names,
      }),
    ).toBe("Alice updated Agent; 42 fields changed");
  });

  it("names a component the flow no longer has by its id", () => {
    expect(
      foldedSummary(entry([fieldWrites("X", ["f"], "upgrade_component")]), t, {
        names,
      }),
    ).toBe("Alice updated X; 1 field changed");
  });

  it("names how many components a multi-component action touched", () => {
    expect(
      foldedSummary(
        entry([
          fieldWrites("A", ["x"], "edit_code"),
          fieldWrites("B", ["x"], "edit_code"),
        ]),
        t,
      ),
    ).toBe("Alice edited the code of 2 components; 2 fields changed");
  });

  it("is null for an entry that does not fold", () => {
    expect(foldedSummary(entry([fieldWrites("A", ["x"])]), t)).toBeNull();
  });
});

describe("summarizeEntry", () => {
  it("falls back to the entry's changes when it does not fold", () => {
    expect(summarizeEntry(entry([fieldWrites("A", ["x"])]), t, { names })).toBe(
      "Edited X on Agent",
    );
  });

  it("is null without operations", () => {
    expect(summarizeEntry({ ...entry([]), operations: null }, t)).toBeNull();
  });
});

describe("describeChanges", () => {
  it("lists every change of a folded entry", () => {
    expect(
      describeChanges(
        [
          fieldWrites("A", ["x"], "restore"),
          {
            ...fieldWrites("B", [], "restore"),
            operation: { type: "add_nodes", nodes: [{ id: "B" }] },
          },
        ],
        t,
        { names },
      ),
    ).toEqual(["Edited X on Agent", "Added Prompt"]);
  });
});
