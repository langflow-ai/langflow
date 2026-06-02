import { renderHook } from "@testing-library/react";
import type { OnSelectionChangeParams } from "@xyflow/react";

import { useCollaborationSelectionSync } from "../use-collaboration-selection-sync";

describe("useCollaborationSelectionSync", () => {
  it("does not send selection updates when collaboration is inactive", () => {
    const sendSelectionUpdate = jest.fn();

    renderHook(() =>
      useCollaborationSelectionSync({
        enabled: false,
        isReady: true,
        lastSelection: {
          nodes: [{ id: "node-1" }],
          edges: [],
        } as OnSelectionChangeParams,
        sendSelectionUpdate,
      }),
    );

    expect(sendSelectionUpdate).not.toHaveBeenCalled();
  });

  it("sends selection updates when collaboration is ready", () => {
    const sendSelectionUpdate = jest.fn();

    const { rerender } = renderHook(
      ({ lastSelection }) =>
        useCollaborationSelectionSync({
          enabled: true,
          isReady: true,
          lastSelection,
          sendSelectionUpdate,
        }),
      {
        initialProps: {
          lastSelection: {
            nodes: [{ id: "node-1" }],
            edges: [],
          } as OnSelectionChangeParams,
        },
      },
    );

    expect(sendSelectionUpdate).toHaveBeenCalledWith({
      kind: "node",
      id: "node-1",
    });

    sendSelectionUpdate.mockClear();
    rerender({
      lastSelection: {
        nodes: [],
        edges: [],
      } as OnSelectionChangeParams,
    });

    expect(sendSelectionUpdate).toHaveBeenCalledWith(null);
  });

  it("clears local selection when collaboration is disabled", () => {
    const sendSelectionUpdate = jest.fn();
    const onLocalSelectionChange = jest.fn();

    const { rerender } = renderHook(
      ({ enabled }) =>
        useCollaborationSelectionSync({
          enabled,
          isReady: true,
          lastSelection: {
            nodes: [{ id: "node-1" }],
            edges: [],
          } as OnSelectionChangeParams,
          sendSelectionUpdate,
          onLocalSelectionChange,
        }),
      { initialProps: { enabled: true } },
    );

    expect(onLocalSelectionChange).toHaveBeenCalledWith({
      kind: "node",
      id: "node-1",
    });

    onLocalSelectionChange.mockClear();
    rerender({ enabled: false });

    expect(onLocalSelectionChange).toHaveBeenCalledWith(null);
    expect(sendSelectionUpdate).toHaveBeenCalledTimes(1);
  });

  it("deduplicates identical selection payloads", () => {
    const sendSelectionUpdate = jest.fn();
    const lastSelection = {
      nodes: [{ id: "node-1" }],
      edges: [],
    } as OnSelectionChangeParams;

    const { rerender } = renderHook(
      ({ revision }) =>
        useCollaborationSelectionSync({
          enabled: true,
          isReady: true,
          lastSelection,
          sendSelectionUpdate,
        }),
      { initialProps: { revision: 0 } },
    );

    expect(sendSelectionUpdate).toHaveBeenCalledTimes(1);
    sendSelectionUpdate.mockClear();

    rerender({ revision: 1 });
    expect(sendSelectionUpdate).not.toHaveBeenCalled();
  });
});
