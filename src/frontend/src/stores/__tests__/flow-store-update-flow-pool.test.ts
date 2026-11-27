import { act } from "@testing-library/react";
import { cloneDeep } from "lodash";
import type { VertexBuildTypeAPI } from "@/types/api";
import type { ChatInputType, ChatOutputType } from "@/types/chat";
import type { FlowPoolType } from "@/types/zustand/flow";
import useFlowStore from "../flowStore";

function freezeDeep<T>(value: T): T {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    Object.values(value).forEach(freezeDeep);
    Object.freeze(value);
  }
  return value;
}

function createEntry(id: string): VertexBuildTypeAPI {
  return {
    id,
    valid: true,
    inactivated_vertices: null,
    next_vertices_ids: [],
    top_level_vertices: [],
    data: {
      results: { text: id },
      outputs: { text: { message: id, type: "text" } },
      logs: { text: [{ name: "log", message: id, type: "info" }] },
      messages: [],
      message: { message: id, sender: "Machine", sender_name: "Bot" },
    },
    timestamp: "2026-01-01T00:00:00Z",
    params: null,
    messages: [],
    artifacts: null,
  };
}

const messages: (ChatInputType | ChatOutputType)[] = [
  { message: "edited input", sender: "User", sender_name: "User" },
  { message: "edited output", sender: "Machine", sender_name: "Bot" },
];

describe("updateFlowPool", () => {
  let pool: FlowPoolType;

  beforeEach(() => {
    jest.clearAllMocks();
    pool = freezeDeep({
      target: [createEntry("build-1"), createEntry("build-2")],
      other: [createEntry("other-build")],
    });
    act(() => useFlowStore.setState({ flowPool: pool }));
  });

  afterEach(() => {
    act(() => useFlowStore.setState({ flowPool: {} }));
  });

  it.each([undefined, "", "build-1", "build-2"])(
    "should replace only the selected result for buildId %s",
    (buildId) => {
      const index = buildId === "build-1" ? 0 : 1;
      const replacement = freezeDeep({
        ...createEntry("replacement"),
        valid: false,
      });
      const before = cloneDeep(pool);

      act(() =>
        useFlowStore.getState().updateFlowPool("target", replacement, buildId),
      );

      const next = useFlowStore.getState().flowPool;
      const expected = [...pool.target];
      expected[index] = replacement;
      expect(next).toEqual({ ...pool, target: expected });
      expect(next).not.toBe(pool);
      expect(next.target).not.toBe(pool.target);
      expect(next.target[index]).toBe(replacement);
      expect(next.target[1 - index]).toBe(pool.target[1 - index]);
      expect(next.other).toBe(pool.other);
      expect(next.other[0]).toBe(pool.other[0]);
      expect(pool).toEqual(before);
    },
  );

  describe.each(messages)("message from $sender", (message) => {
    it.each([undefined, "", "build-1", "build-2"])(
      "should copy only the message ancestors for buildId %s",
      (buildId) => {
        const index = buildId === "build-1" ? 0 : 1;
        const previous = pool.target[index];
        const before = cloneDeep(pool);

        act(() =>
          useFlowStore.getState().updateFlowPool("target", message, buildId),
        );

        const next = useFlowStore.getState().flowPool;
        const updated = next.target[index];
        const expected = [...pool.target];
        expected[index] = { ...previous, data: { ...previous.data, message } };
        expect(next).toEqual({ ...pool, target: expected });
        expect(next).not.toBe(pool);
        expect(next.target).not.toBe(pool.target);
        expect(updated).not.toBe(previous);
        expect(updated.data).not.toBe(previous.data);
        expect(updated.data.message).toBe(message);
        expect(updated.data.results).toBe(previous.data.results);
        expect(updated.data.outputs).toBe(previous.data.outputs);
        expect(updated.data.logs).toBe(previous.data.logs);
        expect(updated.data.messages).toBe(previous.data.messages);
        expect(updated.messages).toBe(previous.messages);
        expect(next.target[1 - index]).toBe(pool.target[1 - index]);
        expect(next.other).toBe(pool.other);
        expect(pool).toEqual(before);
      },
    );
  });

  it("should select the first result with a matching buildId", () => {
    const duplicate = freezeDeep({
      target: [createEntry("same"), createEntry("same")],
    });
    act(() => useFlowStore.setState({ flowPool: duplicate }));

    act(() =>
      useFlowStore.getState().updateFlowPool("target", messages[0], "same"),
    );

    const next = useFlowStore.getState().flowPool;
    expect(next.target[0].data.message).toBe(messages[0]);
    expect(next.target[1]).toBe(duplicate.target[1]);
    expect(duplicate.target[0].data.message?.message).toBe("same");
  });

  it("should preserve successive message snapshots", () => {
    act(() => useFlowStore.getState().updateFlowPool("target", messages[0]));
    const first = freezeDeep(useFlowStore.getState().flowPool);

    act(() => useFlowStore.getState().updateFlowPool("target", messages[1]));

    const second = useFlowStore.getState().flowPool;
    expect(second.target[1].data.message).toBe(messages[1]);
    expect(first.target[1].data.message).toBe(messages[0]);
    expect(pool.target[1].data.message?.message).toBe("build-2");
    expect(second.target[0]).toBe(first.target[0]);
    expect(second.other).toBe(first.other);
  });

  it.each<FlowPoolType>([{}, { other: [createEntry("other")] }])(
    "should leave the store unchanged when the node has no pool: %j",
    (missingPool) => {
      act(() => useFlowStore.setState({ flowPool: freezeDeep(missingPool) }));
      const before = useFlowStore.getState();

      act(() => useFlowStore.getState().updateFlowPool("missing", messages[0]));
      act(() =>
        useFlowStore
          .getState()
          .updateFlowPool("missing", createEntry("replacement")),
      );

      expect(useFlowStore.getState()).toBe(before);
    },
  );

  it.each([undefined, null])(
    "should preserve the no-op for a missing root pool: %s",
    (missingPool) => {
      act(() =>
        useFlowStore.setState({
          flowPool: missingPool as unknown as FlowPoolType,
        }),
      );
      const before = useFlowStore.getState();

      act(() => useFlowStore.getState().updateFlowPool("target", messages[0]));
      act(() =>
        useFlowStore
          .getState()
          .updateFlowPool("target", createEntry("replacement")),
      );

      expect(useFlowStore.getState()).toBe(before);
    },
  );

  describe.each([
    { label: "empty latest", empty: true, buildId: undefined },
    { label: "empty explicit", empty: true, buildId: "absent" },
    { label: "unmatched", empty: false, buildId: "absent" },
  ])("$label result lookup", ({ empty, buildId }) => {
    beforeEach(() => {
      if (empty) {
        pool = freezeDeep({ ...pool, target: [] });
        act(() => useFlowStore.setState({ flowPool: pool }));
      }
    });

    it("should preserve the existing negative-index vertex assignment", () => {
      const replacement = createEntry("replacement");

      act(() =>
        useFlowStore.getState().updateFlowPool("target", replacement, buildId),
      );

      const next = useFlowStore.getState().flowPool;
      expect(next.target[-1]).toBe(replacement);
      expect(next.target).toHaveLength(pool.target.length);
      pool.target.forEach((entry, index) =>
        expect(next.target[index]).toBe(entry),
      );
      expect(next.other).toBe(pool.other);
      expect(pool.target).not.toHaveProperty("-1");
    });

    it("should preserve the message error without committing state", () => {
      const before = useFlowStore.getState();

      expect(() => {
        act(() =>
          useFlowStore
            .getState()
            .updateFlowPool("target", messages[0], buildId),
        );
      }).toThrow(TypeError);

      expect(useFlowStore.getState()).toBe(before);
      expect(pool.target).not.toHaveProperty("-1");
    });
  });
});
