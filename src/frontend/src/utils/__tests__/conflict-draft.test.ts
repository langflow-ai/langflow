import type { FlowType } from "@/types/flow";
import {
  clearAllConflictDrafts,
  clearConflictDraft,
  readConflictDraft,
  saveConflictDraft,
} from "../conflict-draft";

const flow = (
  id: string,
  fields: Record<string, { value: unknown; password?: boolean }> = {},
): FlowType =>
  ({
    id,
    name: "probe",
    description: "",
    data: {
      nodes: [
        {
          id: "n1",
          type: "genericNode",
          position: { x: 0, y: 0 },
          data: {
            id: "n1",
            type: "Component",
            node: {
              display_name: "Node",
              description: "",
              documentation: "",
              template: Object.fromEntries(
                Object.entries(fields).map(([name, spec]) => [
                  name,
                  {
                    type: "str",
                    required: false,
                    list: false,
                    show: true,
                    readonly: false,
                    ...spec,
                  },
                ]),
              ),
            },
          },
        },
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  }) as unknown as FlowType;

describe("conflict drafts", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("should give back the work it was handed", () => {
    expect(saveConflictDraft("user-1", flow("flow-1"), "token-a")).toBe(true);

    const draft = readConflictDraft("user-1", "flow-1");

    expect(draft?.flowId).toBe("flow-1");
    expect(draft?.versionToken).toBe("token-a");
    expect(draft?.data?.nodes).toHaveLength(1);
  });

  it("should never hand one person's work to another", () => {
    saveConflictDraft("user-1", flow("flow-1"), "token-a");

    expect(readConflictDraft("user-2", "flow-1")).toBeNull();
  });

  it("should keep drafts of different flows apart", () => {
    saveConflictDraft("user-1", flow("flow-1"), "token-a");
    saveConflictDraft("user-1", flow("flow-2"), "token-b");

    expect(readConflictDraft("user-1", "flow-1")?.versionToken).toBe("token-a");
    expect(readConflictDraft("user-1", "flow-2")?.versionToken).toBe("token-b");
  });

  it("should not store a secret value", () => {
    saveConflictDraft(
      "user-1",
      flow("flow-1", { api_key: { value: "sk-secret-value", password: true } }),
      "token-a",
    );

    expect(JSON.stringify(localStorage)).not.toContain("sk-secret-value");
  });

  it("should say when secrets were cleared so the restore can admit it", () => {
    saveConflictDraft(
      "user-1",
      flow("flow-1", { api_key: { value: "sk-x", password: true } }),
      "token-a",
    );

    expect(readConflictDraft("user-1", "flow-1")?.secretsCleared).toBe(true);
  });

  it("should not claim secrets were cleared when there were none", () => {
    saveConflictDraft("user-1", flow("flow-1", { text: { value: "hi" } }), "t");

    expect(readConflictDraft("user-1", "flow-1")?.secretsCleared).toBe(false);
  });

  it("should forget a draft once it is cleared", () => {
    saveConflictDraft("user-1", flow("flow-1"), "token-a");

    clearConflictDraft("user-1", "flow-1");

    expect(readConflictDraft("user-1", "flow-1")).toBeNull();
  });

  it("should clear every draft on the browser at logout", () => {
    saveConflictDraft("user-1", flow("flow-1"), "a");
    saveConflictDraft("user-2", flow("flow-2"), "b");
    localStorage.setItem("unrelated_key", "keep me");

    clearAllConflictDrafts();

    expect(readConflictDraft("user-1", "flow-1")).toBeNull();
    expect(readConflictDraft("user-2", "flow-2")).toBeNull();
    expect(localStorage.getItem("unrelated_key")).toBe("keep me");
  });

  it("should return nothing rather than throw on corrupt storage", () => {
    localStorage.setItem("lf_draft_user-1_flow-1", "{not json");

    expect(() => readConflictDraft("user-1", "flow-1")).not.toThrow();
    expect(readConflictDraft("user-1", "flow-1")).toBeNull();
  });

  it("should refuse a draft too large to store instead of throwing", () => {
    const huge = flow("flow-1", { text: { value: "x".repeat(3_000_000) } });

    expect(saveConflictDraft("user-1", huge, "token-a")).toBe(false);
    expect(readConflictDraft("user-1", "flow-1")).toBeNull();
  });

  it("should do nothing without a signed-in user", () => {
    expect(saveConflictDraft(null, flow("flow-1"), "token-a")).toBe(false);
    expect(readConflictDraft(null, "flow-1")).toBeNull();
  });

  it("should survive a storage backend that throws", () => {
    const setItem = jest
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("quota exceeded");
      });

    expect(saveConflictDraft("user-1", flow("flow-1"), "token-a")).toBe(false);

    setItem.mockRestore();
  });
});

describe("reporting what the scrubber actually removed", () => {
  it("should not claim a clear when the scrubber preserved a variable reference", () => {
    // removeApiKeys keeps an api_key holding a global-variable name, so nothing
    // was lost and the restore must not tell the user to re-enter it.
    saveConflictDraft(
      "user-1",
      flow("flow-1", { api_key: { value: "MY_GLOBAL_KEY", password: true } }),
      "token-a",
    );

    expect(readConflictDraft("user-1", "flow-1")?.secretsCleared).toBe(false);
  });

  it("should still report a clear when a real secret was removed", () => {
    saveConflictDraft(
      "user-1",
      flow("flow-1", { token: { value: "sk-live-abc123", password: true } }),
      "token-a",
    );

    const draft = readConflictDraft("user-1", "flow-1");
    expect(draft?.secretsCleared).toBe(true);
    expect(JSON.stringify(localStorage)).not.toContain("sk-live-abc123");
  });
});
