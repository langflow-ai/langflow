import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import HumanInputCard from "@/components/core/chatComponents/HumanInputCard";
import {
  Popover,
  PopoverAnchor,
  PopoverContentWithoutPortal,
} from "@/components/ui/popover";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { useHitlStore } from "@/stores/hitlStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";

/**
 * Whether this node is awaiting a human decision on the canvas. The Playground renders
 * its own card, so the canvas affordance only shows while the Playground is closed.
 */
export function useAwaitingHumanInput(nodeId: string): boolean {
  const pending = useHitlStore((state) =>
    state.pending?.nodeId === nodeId ? state.pending : null,
  );
  const playgroundOpen = usePlaygroundStore((state) => state.isOpen);
  return Boolean(pending) && !playgroundOpen;
}

/**
 * Canvas affordance for a paused Human Input node (LE-1603): a pause icon rendered in the
 * node's run-button slot (same size/style as the play icon) that anchors a decision popover.
 * The popover reuses the chat `HumanInputCard` (which self-resumes), so the human can
 * resolve the pause from the canvas. Only the node whose id matches the pending request
 * renders anything.
 */
export default function HumanInputNodeBadge({ nodeId }: { nodeId: string }) {
  const { t } = useTranslation();
  const pending = useHitlStore((state) =>
    state.pending?.nodeId === nodeId ? state.pending : null,
  );
  const awaiting = useAwaitingHumanInput(nodeId);
  const [open, setOpen] = useState(false);

  // Auto-open on every NEW pause (keyed by request_id): a rerun supersedes the old
  // pause, and its popover must resurface even if the previous one was dismissed.
  const requestId = pending?.content.request_id;
  useEffect(() => {
    if (awaiting && requestId) setOpen(true);
  }, [awaiting, requestId]);

  if (!pending || !awaiting) return null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <button
          type="button"
          data-testid="human-input-node-badge"
          onClick={() => setOpen(true)}
          title={t("humanInput.awaitingInput")}
          aria-label={t("humanInput.awaitingInput")}
          className="nodrag flex items-center justify-center"
        >
          <IconComponent
            name="Pause"
            className="h-3.5 w-3.5 text-accent-indigo-foreground"
            strokeWidth={ICON_STROKE_WIDTH}
          />
        </button>
      </PopoverAnchor>
      {/* Non-portaled so the card lives inside the node subtree and inherits the canvas
          transform — a body portal repositions late on zoom and visibly lags the node. */}
      <PopoverContentWithoutPortal
        side="bottom"
        align="start"
        className="w-96 overflow-hidden rounded-xl border-0 p-0 shadow-md"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <HumanInputCard content={pending.content} />
      </PopoverContentWithoutPortal>
    </Popover>
  );
}
