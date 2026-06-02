import { type MutableRefObject, useEffect } from "react";

import { serializeCollaborationSelectionTarget } from "@/hooks/flows/collaboration-selection-target";
import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";

export type UseCollaborationSelectionResendOnReadyOptions = {
  enabled: boolean;
  isReady: boolean;
  getPendingTarget: () => CollaborationSelectionTarget | null;
  lastSentRef: MutableRefObject<string | null>;
  sendSelectionUpdate: (target: CollaborationSelectionTarget | null) => void;
};

/** Resend the latest pending selection when collaboration becomes ready (or beta is re-enabled). */
export function useCollaborationSelectionResendOnReady({
  enabled,
  isReady,
  getPendingTarget,
  lastSentRef,
  sendSelectionUpdate,
}: UseCollaborationSelectionResendOnReadyOptions): void {
  useEffect(() => {
    if (!enabled) {
      lastSentRef.current = null;
      return;
    }

    if (!isReady) {
      lastSentRef.current = null;
      return;
    }

    const target = getPendingTarget();
    const serialized = serializeCollaborationSelectionTarget(target);
    if (lastSentRef.current === serialized) {
      return;
    }

    lastSentRef.current = serialized;
    sendSelectionUpdate(target);
  }, [enabled, isReady, getPendingTarget, lastSentRef, sendSelectionUpdate]);
}
