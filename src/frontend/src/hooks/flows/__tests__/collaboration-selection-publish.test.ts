import { renderHook } from "@testing-library/react";
import { useRef } from "react";

import {
  clearCollaborationSelectionPublishState,
  publishCollaborationSelection,
} from "../collaboration-selection-publish";

describe("collaboration-selection-publish", () => {
  it("publishes local selection immediately and sends when ready", () => {
    const sendSelectionUpdate = jest.fn();
    const onLocalSelectionChange = jest.fn();

    renderHook(() => {
      const lastSentRef = useRef<string | null>(null);

      publishCollaborationSelection(
        { kind: "node", id: "node-1" },
        {
          enabled: true,
          isReady: true,
          lastSentRef,
          sendSelectionUpdate,
        },
        { onLocalSelectionChange },
      );
    });

    expect(onLocalSelectionChange).toHaveBeenCalledWith({
      kind: "node",
      id: "node-1",
    });
    expect(sendSelectionUpdate).toHaveBeenCalledWith({
      kind: "node",
      id: "node-1",
    });
  });

  it("does not send when collaboration is not ready", () => {
    const sendSelectionUpdate = jest.fn();

    renderHook(() => {
      const lastSentRef = useRef<string | null>(null);

      publishCollaborationSelection(
        { kind: "node", id: "node-1" },
        {
          enabled: true,
          isReady: false,
          lastSentRef,
          sendSelectionUpdate,
        },
      );
    });

    expect(sendSelectionUpdate).not.toHaveBeenCalled();
  });

  it("clears last-sent and local selection state", () => {
    const onLocalSelectionChange = jest.fn();

    renderHook(() => {
      const lastSentRef = useRef<string | null>("node:node-1");

      clearCollaborationSelectionPublishState(
        lastSentRef,
        onLocalSelectionChange,
      );

      expect(lastSentRef.current).toBeNull();
    });

    expect(onLocalSelectionChange).toHaveBeenCalledWith(null);
  });
});
