import { Background, Panel } from "@xyflow/react";
import { memo } from "react";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CanvasControlButton from "@/components/core/canvasControlsComponent/CanvasControlButton";
import CanvasControls from "@/components/core/canvasControlsComponent/CanvasControls";
import LogCanvasControls from "@/components/core/logCanvasControlsComponent";
import { Button } from "@/components/ui/button";

import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { useSearchContext } from "../flowSidebarComponent";
import { NAV_ITEMS } from "../flowSidebarComponent/components/sidebarSegmentedNav";

export const MemoizedBackground = memo(() => (
  <Background size={2} gap={20} className="" />
));

interface MemoizedCanvasControlsProps {
  setIsAddingNote: (value: boolean) => void;
  shadowBoxWidth: number;
  shadowBoxHeight: number;
}

export const MemoizedLogCanvasControls = memo(() => <LogCanvasControls />);

export const MemoizedCanvasControls = memo(
  ({
    setIsAddingNote,
    shadowBoxWidth,
    shadowBoxHeight,
  }: MemoizedCanvasControlsProps) => {
    const isLocked = useFlowStore(
      useShallow((state) => state.currentFlow?.locked),
    );

    return (
      <CanvasControls>
        <Button
          unstyled
          unselectable="on"
          size="icon"
          data-testid="lock-status"
          className="flex items-center justify-center px-2 rounded-none gap-1 cursor-default"
          title={`Lock status: ${isLocked ? "Locked" : "Unlocked"}`}
        >
          <ForwardedIconComponent
            name={isLocked ? "Lock" : "Unlock"}
            className={cn(
              "!h-[18px] !w-[18px] text-muted-foreground",
              isLocked && "text-destructive",
            )}
          />
          {isLocked && (
            <span className="text-xs text-destructive">Flow Locked</span>
          )}
        </Button>
      </CanvasControls>
    );
  },
);
