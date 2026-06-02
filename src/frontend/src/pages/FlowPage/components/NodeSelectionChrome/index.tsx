import type { ReactNode } from "react";
import { useNodeCollaborationParticipants } from "@/hooks/flows/use-node-collaboration-participants";
import CollaborationSelectionBump from "@/pages/FlowPage/components/CollaborationSelectionBump";
import {
  NODE_SELECTION_CHROME_BUMP_SLOT_CLASS,
  NODE_SELECTION_CHROME_ROW_CLASS,
  NODE_SELECTION_CHROME_TOOLBAR_SLOT_CLASS,
  NODE_SELECTION_CHROME_TOP_CLASS,
} from "@/pages/FlowPage/components/NodeSelectionChrome/constants";
import { cn } from "@/utils/utils";

type NodeSelectionChromeProps = {
  nodeId: string;
  toolbar: ReactNode;
  trailing?: ReactNode;
  className?: string;
  zIndexClass?: string;
};

export default function NodeSelectionChrome({
  nodeId,
  toolbar,
  trailing,
  className,
  zIndexClass = "z-50",
}: NodeSelectionChromeProps): JSX.Element {
  const participants = useNodeCollaborationParticipants(nodeId);

  return (
    <div
      className={cn(
        NODE_SELECTION_CHROME_ROW_CLASS,
        NODE_SELECTION_CHROME_TOP_CLASS,
        zIndexClass,
        "transform transition-all duration-300 ease-out",
        className,
      )}
      data-testid="node-selection-chrome"
    >
      <div className={NODE_SELECTION_CHROME_BUMP_SLOT_CLASS}>
        {participants.length > 0 ? (
          <CollaborationSelectionBump participants={participants} />
        ) : null}
      </div>
      <div className={NODE_SELECTION_CHROME_TOOLBAR_SLOT_CLASS}>{toolbar}</div>
      <div className="pointer-events-auto flex min-w-8 flex-1 items-center justify-end">
        {trailing}
      </div>
    </div>
  );
}
