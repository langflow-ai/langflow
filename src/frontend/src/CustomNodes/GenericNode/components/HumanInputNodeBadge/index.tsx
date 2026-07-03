import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
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
 * Canvas affordance for a paused Human Input node (LE-1603): a circular indigo "awaiting
 * input" badge that doubles as the anchor for a decision popover. The popover reuses the chat
 * `HumanInputCard` (which self-resumes), so the human can resolve the pause from the
 * canvas. Only the node whose id matches the pending request renders anything.
 */
export default function HumanInputNodeBadge({ nodeId }: { nodeId: string }) {
  const { t } = useTranslation();
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
          title={t("humanInput.awaitingInput")}
          aria-label={t("humanInput.awaitingInput")}
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
            "border-2 border-accent-indigo-foreground text-accent-indigo-foreground",
          )}
        >
          <span className="flex items-center gap-[2px]">
            <span className="h-2 w-0.5 rounded-[1px] bg-accent-indigo-foreground" />
            <span className="h-2 w-0.5 rounded-[1px] bg-accent-indigo-foreground" />
          </span>
        </button>
      </PopoverAnchor>
      <PopoverContent
        side="bottom"
        align="start"
        className="w-96 overflow-hidden rounded-xl border-0 p-0 shadow-md"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <HumanInputCard content={pending.content} />
      </PopoverContent>
    </Popover>
  );
}
