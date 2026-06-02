import type { OnSelectionChangeParams } from "@xyflow/react";
import { useEffect, useRef } from "react";

import { publishCollaborationSelection } from "@/hooks/flows/collaboration-selection-publish";
import {
  selectionTargetFromFlowSelection,
  serializeCollaborationSelectionTarget,
} from "@/hooks/flows/collaboration-selection-target";
import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";

export type UseCollaborationSelectionSyncOptions = {
  enabled: boolean;
  isReady: boolean;
  lastSelection: OnSelectionChangeParams | null;
  sendSelectionUpdate: (selected: CollaborationSelectionTarget | null) => void;
  onLocalSelectionChange?: (
    selected: CollaborationSelectionTarget | null,
  ) => void;
};

/** Sync React Flow selection state to collaboration when enabled and ready. */
export function useCollaborationSelectionSync({
  enabled,
  isReady,
  lastSelection,
  sendSelectionUpdate,
  onLocalSelectionChange,
}: UseCollaborationSelectionSyncOptions): void {
  const lastSentSelectionRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      lastSentSelectionRef.current = null;
      onLocalSelectionChange?.(null);
      return;
    }

    if (!isReady) {
      lastSentSelectionRef.current = null;
      return;
    }

    const target = selectionTargetFromFlowSelection(lastSelection);
    const serialized = serializeCollaborationSelectionTarget(target);
    if (lastSentSelectionRef.current === serialized) {
      return;
    }

    publishCollaborationSelection(
      target,
      {
        enabled,
        isReady,
        lastSentRef: lastSentSelectionRef,
        sendSelectionUpdate,
      },
      { onLocalSelectionChange },
    );
  }, [
    enabled,
    isReady,
    lastSelection,
    onLocalSelectionChange,
    sendSelectionUpdate,
  ]);
}
