import type { MutableRefObject } from "react";
import { flushSync } from "react-dom";

import { serializeCollaborationSelectionTarget } from "@/hooks/flows/collaboration-selection-target";
import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";

export type CollaborationSelectionPublishContext = {
  enabled: boolean;
  isReady: boolean;
  lastSentRef: MutableRefObject<string | null>;
  sendSelectionUpdate: (target: CollaborationSelectionTarget | null) => void;
};

export function publishCollaborationSelection(
  target: CollaborationSelectionTarget | null,
  ctx: CollaborationSelectionPublishContext,
  options?: {
    onLocalSelectionChange?: (
      target: CollaborationSelectionTarget | null,
    ) => void;
    flushLocal?: boolean;
  },
): void {
  if (!ctx.enabled) {
    return;
  }

  if (options?.onLocalSelectionChange) {
    if (options.flushLocal) {
      flushSync(() => options.onLocalSelectionChange?.(target));
    } else {
      options.onLocalSelectionChange(target);
    }
  }

  const serialized = serializeCollaborationSelectionTarget(target);
  if (ctx.isReady && ctx.lastSentRef.current !== serialized) {
    ctx.lastSentRef.current = serialized;
    ctx.sendSelectionUpdate(target);
  }
}

export function clearCollaborationSelectionPublishState(
  lastSentRef: MutableRefObject<string | null>,
  onLocalSelectionChange?: (
    target: CollaborationSelectionTarget | null,
  ) => void,
): void {
  lastSentRef.current = null;
  onLocalSelectionChange?.(null);
}
