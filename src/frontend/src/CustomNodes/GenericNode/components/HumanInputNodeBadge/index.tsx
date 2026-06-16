import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import HumanInputCard from "@/components/core/chatComponents/HumanInputCard";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import { useHitlStore } from "@/stores/hitlStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { cn } from "@/utils/utils";

/**
 * Canvas affordance for a paused Human Input node (LE-1603): a pulsing "awaiting input"
 * badge that doubles as the anchor for a decision popover. The popover reuses the chat
 * `HumanInputCard` (which self-resumes), so the human can resolve the pause from the
 * canvas. Only the node whose id matches the pending request renders anything.
 */
export default function HumanInputNodeBadge({ nodeId }: { nodeId: string }) {
  const pending = useHitlStore((state) =>
    state.pending?.nodeId === nodeId ? state.pending : null,
  );
  // The Playground renders its own card; its anchored popover would otherwise portal
  // over the open Playground. Only surface the canvas affordance when it is closed.
  const playgroundOpen = usePlaygroundStore((state) => state.isOpen);
  const [open, setOpen] = useState(false);

  // Auto-open when this node starts awaiting; dismissing keeps the badge to reopen.
  useEffect(() => {
    if (pending && !playgroundOpen) setOpen(true);
  }, [pending, playgroundOpen]);

  if (!pending || playgroundOpen) return null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <button
          type="button"
          data-testid="human-input-node-badge"
          onClick={() => setOpen(true)}
          className={cn(
            "flex items-center gap-1 rounded-full border border-accent-amber-foreground/40",
            "bg-accent-amber/20 px-2 py-0.5 text-xs font-medium text-accent-amber-foreground",
          )}
        >
          <ForwardedIconComponent
            name="CircleHelp"
            className="h-3 w-3 animate-pulse"
          />
          Awaiting input
        </button>
      </PopoverAnchor>
      <PopoverContent
        side="bottom"
        align="start"
        className="w-96 p-0"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <HumanInputCard content={pending.content} />
      </PopoverContent>
    </Popover>
  );
}
