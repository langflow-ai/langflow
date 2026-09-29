import type { FlowType } from "@/types/flow";
import type { FlowConflict } from "../flowConflictStore";
import { useFlowConflictStore } from "../flowConflictStore";

const conflict = (overrides: Partial<FlowConflict> = {}): FlowConflict => ({
  flowId: "flow-1",
  author: { id: "user-2", username: "carlos" },
  isSelf: false,
  modifiedAt: "2026-09-02T10:00:00Z",
  expectedToken: "token-a",
  currentToken: "token-b",
  theirFlow: null,
  ...overrides,
});

describe("flowConflictStore", () => {
  beforeEach(() => {
    useFlowConflictStore.setState({
      conflict: null,
      dialogOpen: false,
      abandonedFlowIds: new Set<string>(),
    });
  });

  it("should start with no conflict and a closed dialog", () => {
    const state = useFlowConflictStore.getState();
    expect(state.conflict).toBeNull();
    expect(state.dialogOpen).toBe(false);
  });

  it("should record a conflict without opening the dialog", () => {
    useFlowConflictStore.getState().setConflict(conflict());

    const state = useFlowConflictStore.getState();
    expect(state.conflict?.author.username).toBe("carlos");
    expect(state.dialogOpen).toBe(false);
  });

  it("should keep the first conflict so the dialog does not change under the reader", () => {
    useFlowConflictStore.getState().setConflict(conflict());
    useFlowConflictStore
      .getState()
      .setConflict(conflict({ author: { id: "user-3", username: "ana" } }));

    expect(useFlowConflictStore.getState().conflict?.author.username).toBe(
      "carlos",
    );
  });

  it("should accept a conflict for a different flow", () => {
    useFlowConflictStore.getState().setConflict(conflict());
    useFlowConflictStore.getState().setConflict(conflict({ flowId: "flow-2" }));

    expect(useFlowConflictStore.getState().conflict?.flowId).toBe("flow-2");
  });

  it("should attach the other version once it arrives", () => {
    useFlowConflictStore.getState().setConflict(conflict());
    useFlowConflictStore
      .getState()
      .setTheirFlow({ id: "flow-1", name: "theirs" } as FlowType);

    expect(useFlowConflictStore.getState().conflict?.theirFlow?.name).toBe(
      "theirs",
    );
  });

  it("should ignore a late version when the conflict is already cleared", () => {
    useFlowConflictStore.getState().setTheirFlow({ id: "flow-1" } as FlowType);

    expect(useFlowConflictStore.getState().conflict).toBeNull();
  });

  it("should open and close the dialog without losing the conflict", () => {
    useFlowConflictStore.getState().setConflict(conflict());
    useFlowConflictStore.getState().openDialog();
    expect(useFlowConflictStore.getState().dialogOpen).toBe(true);

    useFlowConflictStore.getState().closeDialog();
    expect(useFlowConflictStore.getState().dialogOpen).toBe(false);
    expect(useFlowConflictStore.getState().conflict).not.toBeNull();
  });

  it("should clear the conflict and close the dialog together", () => {
    useFlowConflictStore.getState().setConflict(conflict());
    useFlowConflictStore.getState().openDialog();

    useFlowConflictStore.getState().clearConflict();

    const state = useFlowConflictStore.getState();
    expect(state.conflict).toBeNull();
    expect(state.dialogOpen).toBe(false);
  });

  it("should mark a duplicated flow as abandoned", () => {
    useFlowConflictStore.getState().setConflict(conflict());

    useFlowConflictStore.getState().abandonFlow("flow-1");

    const state = useFlowConflictStore.getState();
    expect(state.conflict).toBeNull();
    expect(state.abandonedFlowIds.has("flow-1")).toBe(true);
  });

  it("should never re-open a conflict on an abandoned flow", () => {
    useFlowConflictStore.getState().abandonFlow("flow-1");

    useFlowConflictStore.getState().setConflict(conflict());

    expect(useFlowConflictStore.getState().conflict).toBeNull();
  });

  it("should still allow conflicts on other flows after one is abandoned", () => {
    useFlowConflictStore.getState().abandonFlow("flow-1");

    useFlowConflictStore.getState().setConflict(conflict({ flowId: "flow-9" }));

    expect(useFlowConflictStore.getState().conflict?.flowId).toBe("flow-9");
  });
});

describe("returning to an abandoned flow", () => {
  beforeEach(() => {
    useFlowConflictStore.setState({
      conflict: null,
      dialogOpen: false,
      abandonedFlowIds: new Set<string>(),
    });
  });

  it("should let a reopened flow be written and conflict again", () => {
    useFlowConflictStore.getState().abandonFlow("flow-1");

    useFlowConflictStore.getState().resumeFlow("flow-1");

    expect(useFlowConflictStore.getState().abandonedFlowIds.has("flow-1")).toBe(
      false,
    );
    useFlowConflictStore.getState().setConflict(conflict());
    expect(useFlowConflictStore.getState().conflict?.flowId).toBe("flow-1");
  });

  it("should leave other abandoned flows alone", () => {
    useFlowConflictStore.getState().abandonFlow("flow-1");
    useFlowConflictStore.getState().abandonFlow("flow-2");

    useFlowConflictStore.getState().resumeFlow("flow-1");

    expect(useFlowConflictStore.getState().abandonedFlowIds.has("flow-2")).toBe(
      true,
    );
  });

  it("should be a no-op for a flow that was never abandoned", () => {
    const before = useFlowConflictStore.getState().abandonedFlowIds;

    useFlowConflictStore.getState().resumeFlow("flow-9");

    expect(useFlowConflictStore.getState().abandonedFlowIds).toBe(before);
  });
});

describe("refreshing a conflict the server moved past", () => {
  beforeEach(() => {
    useFlowConflictStore.setState({
      conflict: null,
      dialogOpen: false,
      abandonedFlowIds: new Set<string>(),
    });
  });

  const conflictFor = (currentToken: string) => ({
    flowId: "flow-1",
    author: { id: "user-2", username: "carlos" },
    isSelf: false,
    modifiedAt: "2026-09-02T10:00:00Z",
    expectedToken: "token-a",
    currentToken,
    theirFlow: null,
  });

  it("should replace the token setConflict deliberately refuses to change", () => {
    useFlowConflictStore.getState().setConflict(conflictFor("token-b"));

    useFlowConflictStore.getState().setConflict(conflictFor("token-c"));
    expect(useFlowConflictStore.getState().conflict?.currentToken).toBe(
      "token-b",
    );

    // An overwrite refused for staleness has to be able to move the token on, or
    // the dialog can only ever resend the write the server just rejected.
    useFlowConflictStore.getState().refreshConflict(conflictFor("token-c"));
    expect(useFlowConflictStore.getState().conflict?.currentToken).toBe(
      "token-c",
    );
  });

  it("should still refuse to resurrect an abandoned flow", () => {
    useFlowConflictStore.getState().abandonFlow("flow-1");

    useFlowConflictStore.getState().refreshConflict(conflictFor("token-c"));

    expect(useFlowConflictStore.getState().conflict).toBeNull();
  });
});
