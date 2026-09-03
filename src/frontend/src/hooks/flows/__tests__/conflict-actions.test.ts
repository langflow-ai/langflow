import { api } from "@/controllers/API/api";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import {
  adoptServerVersion,
  attachTheirFlow,
  fetchAndAdoptServerVersion,
  readFlowVersionState,
  registerConflictState,
} from "../conflict-actions";

jest.mock("@/controllers/API/api", () => ({
  api: { get: jest.fn() },
}));

jest.mock("@/utils/reactflowUtils", () => ({
  ...jest.requireActual("@/utils/reactflowUtils"),
  processFlows: jest.fn(),
}));

const mockGet = api.get as jest.Mock;

const serverFlow = (id = "flow-1"): FlowType =>
  ({
    id,
    name: "theirs",
    description: "",
    version_token: "token-server",
    data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
  }) as unknown as FlowType;

const conflictInput = (overrides = {}) => ({
  flowId: "flow-1",
  authorId: "user-2",
  authorName: "carlos",
  modifiedAt: "2026-09-02T10:00:00Z",
  expectedToken: "token-a",
  currentToken: "token-b",
  currentUserId: "user-1",
  ...overrides,
});

describe("conflict actions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useFlowConflictStore.setState({
      conflict: null,
      dialogOpen: false,
      abandonedFlowIds: new Set<string>(),
    });
    useFlowsManagerStore.setState({
      currentFlow: undefined,
      currentFlowId: "",
    });
  });

  describe("adopting the server's version", () => {
    it("should move the baseline so the next save carries a current token", () => {
      adoptServerVersion(serverFlow());

      const baseline = useFlowsManagerStore.getState().currentFlow;
      expect(baseline?.id).toBe("flow-1");
      expect(baseline?.version_token).toBe("token-server");
    });

    it("should not hand the caller's object to the store", () => {
      // The stores mutate what they are given; sharing the fetched object would
      // let a later hydration write back through the caller's reference.
      const fetched = serverFlow();

      adoptServerVersion(fetched);

      expect(useFlowsManagerStore.getState().currentFlow).not.toBe(fetched);
    });

    it("should adopt what the server returns", async () => {
      mockGet.mockResolvedValueOnce({ data: serverFlow() });

      await expect(fetchAndAdoptServerVersion("flow-1")).resolves.toBe(true);
      expect(useFlowsManagerStore.getState().currentFlow?.id).toBe("flow-1");
    });

    it("should report failure rather than throw when the fetch fails", async () => {
      mockGet.mockRejectedValueOnce(new Error("offline"));

      await expect(fetchAndAdoptServerVersion("flow-1")).resolves.toBe(false);
      expect(useFlowsManagerStore.getState().currentFlow).toBeUndefined();
    });
  });

  describe("reading the version state", () => {
    it("should return the state the server reports", async () => {
      mockGet.mockResolvedValueOnce({
        data: {
          version_token: "token-b",
          last_modified_by: "user-2",
          last_modified_by_username: "carlos",
          updated_at: null,
        },
      });

      await expect(readFlowVersionState("flow-1")).resolves.toMatchObject({
        version_token: "token-b",
      });
    });

    it("should return null instead of throwing, so it never blocks what it guards", async () => {
      mockGet.mockRejectedValueOnce(new Error("boom"));

      await expect(readFlowVersionState("flow-1")).resolves.toBeNull();
    });
  });

  describe("registering the conflict", () => {
    it("should name the other person", () => {
      registerConflictState(conflictInput());

      const conflict = useFlowConflictStore.getState().conflict;
      expect(conflict?.author.username).toBe("carlos");
      expect(conflict?.isSelf).toBe(false);
    });

    it("should recognise the other writer as me, for the another-tab wording", () => {
      registerConflictState(
        conflictInput({ authorId: "user-1", currentUserId: "user-1" }),
      );

      expect(useFlowConflictStore.getState().conflict?.isSelf).toBe(true);
    });

    it("should not claim it was me when the author is unknown", () => {
      registerConflictState(
        conflictInput({ authorId: null, currentUserId: null }),
      );

      expect(useFlowConflictStore.getState().conflict?.isSelf).toBe(false);
    });

    it("should carry both tokens so the dialog can explain itself", () => {
      registerConflictState(conflictInput());

      const conflict = useFlowConflictStore.getState().conflict;
      expect(conflict?.expectedToken).toBe("token-a");
      expect(conflict?.currentToken).toBe("token-b");
    });

    it("should leave the dialog closed until the person asks for it", () => {
      registerConflictState(conflictInput());

      expect(useFlowConflictStore.getState().dialogOpen).toBe(false);
    });
  });

  describe("attaching their version for the diff", () => {
    it("should store what the server returns", async () => {
      registerConflictState(conflictInput());
      mockGet.mockResolvedValueOnce({ data: serverFlow() });

      await attachTheirFlow("flow-1");

      expect(useFlowConflictStore.getState().conflict?.theirFlow?.id).toBe(
        "flow-1",
      );
    });

    it("should degrade to my-changes-only rather than break the exit", async () => {
      registerConflictState(conflictInput());
      mockGet.mockRejectedValueOnce(new Error("offline"));

      await expect(attachTheirFlow("flow-1")).resolves.toBeUndefined();
      expect(useFlowConflictStore.getState().conflict).not.toBeNull();
      expect(useFlowConflictStore.getState().conflict?.theirFlow).toBeNull();
    });
  });
});

describe("adopting a version onto the canvas", () => {
  it("should put the server's graph on the canvas, not only in the baseline", async () => {
    const { adoptServerVersionOnCanvas } = await import("../adopt-version-on-canvas");
    const merged = {
      ...serverFlow(),
      data: {
        nodes: [
          {
            id: "merged-node",
            type: "genericNode",
            position: { x: 0, y: 0 },
            data: {
              id: "merged-node",
              type: "ChatInput",
              node: { template: {}, outputs: [] },
            },
          },
        ],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    } as unknown as FlowType;

    adoptServerVersionOnCanvas(merged);

    // Leaving the canvas on the author's own graph would drop whatever they took
    // from the other person, and the next autosave would write that loss back.
    const nodes = useFlowStore.getState().nodes;
    expect(nodes.map((n) => n.id)).toEqual(["merged-node"]);
  });

  it("should not treat an adopted version as unsaved work", async () => {
    const { adoptServerVersionOnCanvas } = await import("../adopt-version-on-canvas");
    useFlowStore.setState({ userEditedSinceLoad: true });

    adoptServerVersionOnCanvas(serverFlow());

    expect(useFlowStore.getState().userEditedSinceLoad).toBe(false);
  });
});
