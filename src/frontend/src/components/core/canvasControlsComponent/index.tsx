import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn, getOS } from "@/utils/utils";
import {
  ControlButton,
  Panel,
  type ReactFlowState,
  useReactFlow,
  useStore,
  useStoreApi,
} from "@xyflow/react";
import { cloneDeep } from "lodash";
import { useCallback, useEffect, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { shallow } from "zustand/shallow";

type CustomControlButtonProps = {
  iconName?: string;
  tooltipText: string;
  onClick: () => void;
  disabled?: boolean;
  backgroundClasses?: string;
  iconClasses?: string;
  testId?: string;
  name?: string;
  shortcut?: string;
};

export const CustomControlButton = ({
  iconName = "",
  tooltipText,
  onClick,
  disabled,
  backgroundClasses,
  iconClasses,
  testId,
}: CustomControlButtonProps): JSX.Element => {
  return (
    <ControlButton
      data-testid={testId}
      className="group"
      onClick={onClick}
      disabled={disabled}
      title={testId?.replace(/_/g, " ")}
    >
      <ShadTooltip content={tooltipText} side="right">
        <div className={cn("rounded p-2.5 flex items-center justify-center", backgroundClasses)}>
          <IconComponent
            name={iconName}
            aria-hidden="true"
            className={cn(
              "text-muted-foreground group-hover:text-primary !h-5 !w-5 ",
              iconClasses,
            )}
          />
        </div>
      </ShadTooltip>
    </ControlButton>
  );
};

// New component for dropdown control buttons
const DropdownControlButton = ({
  iconName = "",
  tooltipText,
  onClick,
  disabled,
  backgroundClasses,
  iconClasses,
  testId,
  name = "",
  shortcut = "",
}: CustomControlButtonProps): JSX.Element => {
  return (
    <Button
      data-testid={testId}
      className={cn(
        "group flex items-center justify-center !py-1.5 !px-3 hover:bg-accent h-full rounded-none",
        disabled && "cursor-not-allowed opacity-50",
      )}
      onClick={onClick}
      variant="ghost"
      disabled={disabled}
      title={testId?.replace(/_/g, " ")}
    >
      <div
        className={cn(
          "flex flex-row items-center justify-between w-full h-full",
          backgroundClasses,
        )}
      >
        <span className="text-muted-foreground text-sm mr-2 text-muted-foreground">
          {name}
        </span>
        <div className="flex flex-row items-center justify-center gap-1 text-sm text-placeholder-foreground w-[24px]">
          <div className="mr-1">{getModifierKey()}</div>
          <div>{shortcut}</div>
        </div>
      </div>
    </Button>
  );
};

// Helper function to get OS-specific modifier key
const getModifierKey = () => {
  const os = getOS();
  return os === "macos" ? "⌘" : "Ctrl";
};

const selector = (s: ReactFlowState) => ({
  isInteractive: s.nodesDraggable || s.nodesConnectable || s.elementsSelectable,
  minZoomReached: s.transform[2] <= s.minZoom,
  maxZoomReached: s.transform[2] >= s.maxZoom,
});

const CanvasControls = ({ children }) => {
  const store = useStoreApi();
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const { isInteractive, minZoomReached, maxZoomReached } = useStore(
    selector,
    shallow,
  );
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const saveFlow = useSaveFlow();
  const isLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const setHelperLineEnabled = useFlowStore(
    (state) => state.setHelperLineEnabled,
  );
  const helperLineEnabled = useFlowStore((state) => state.helperLineEnabled);

  useEffect(() => {
    store.setState({
      nodesDraggable: !isLocked,
      nodesConnectable: !isLocked,
      elementsSelectable: !isLocked,
    });
  }, [isLocked]);

  const handleSaveFlow = useCallback(() => {
    const currentFlow = useFlowStore.getState().currentFlow;
    if (!currentFlow) return;
    const newFlow = cloneDeep(currentFlow);
    newFlow.locked = isInteractive;
    if (autoSaving) {
      saveFlow(newFlow);
    } else {
      setCurrentFlow(newFlow);
    }
  }, [isInteractive, autoSaving, saveFlow, setCurrentFlow]);

  const onToggleInteractivity = useCallback(() => {
    store.setState({
      nodesDraggable: !isInteractive,
      nodesConnectable: !isInteractive,
      elementsSelectable: !isInteractive,
    });
    handleSaveFlow();
    setDropdownOpen(false);
  }, [isInteractive, store, handleSaveFlow]);

  const onToggleHelperLines = useCallback(() => {
    setHelperLineEnabled(!helperLineEnabled);
    setDropdownOpen(false);
  }, [setHelperLineEnabled, helperLineEnabled]);

  const handleZoomIn = useCallback(() => {
    zoomIn();
    setDropdownOpen(false);
  }, [zoomIn]);

  const handleZoomOut = useCallback(() => {
    zoomOut();
    setDropdownOpen(false);
  }, [zoomOut]);

  const handleFitView = useCallback(() => {
    fitView();
    setDropdownOpen(false);
  }, [fitView]);

  const size = "100%"

  return (
    <Panel
      data-testid="main_canvas_controls"
      className="react-flow__controls !left-auto !m-2 flex !flex-row gap-1.5 rounded-md border border-border bg-background fill-foreground stroke-foreground text-primary [&>button]:border-0 [&>button]:bg-background hover:[&>button]:bg-accent"
      position="bottom-right"
    >
      {children}
      {children && (
        <span>
          <Separator orientation="vertical" />
        </span>
      )}
      {/* Dropdown with all controls */}
      <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            data-testid="canvas_controls_dropdown"
            className="group  rounded !p-0"
            title="Canvas Controls"
          >
            <ShadTooltip content="Canvas Controls" side="top" align="end">
              <div className="rounded py-2.5 px-1 flex items-center justify-center">
                <div className="text-sm text-primary pr-2">{size}</div>
                <IconComponent
                  name={dropdownOpen ? "ChevronDown" : "ChevronUp"}
                  aria-hidden="true"
                  className="text-primary group-hover:text-primary !h-5 !w-5"
                />
              </div>
            </ShadTooltip>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side="top"
          align="end"
          className="flex flex-col w-full"
        >
          <DropdownControlButton
            // iconName="ZoomIn"
            tooltipText="Zoom In"
            onClick={handleZoomIn}
            disabled={maxZoomReached}
            testId="zoom_in_dropdown"
            name="Zoom In"
            shortcut={`+`}
          />
          <DropdownControlButton
            tooltipText="Zoom Out"
            onClick={handleZoomOut}
            disabled={minZoomReached}
            testId="zoom_out_dropdown"
            name="Zoom Out"
            shortcut={`-`}
          />
          <Separator />
          <DropdownControlButton
            tooltipText="Fit To Zoom"
            onClick={handleFitView}
            testId="fit_view_dropdown"
            name="Zoom To 100%"
            shortcut={`0`}
          />
          <DropdownControlButton
            tooltipText="Fit To Zoom"
            onClick={handleFitView}
            testId="fit_view_dropdown"
            name="Zoom To Fit"
            shortcut={`1`}
          />

          {/* <DropdownControlButton
            iconName={isInteractive ? "LockOpen" : "Lock"}
            tooltipText={isInteractive ? "Lock" : "Unlock"}
            onClick={onToggleInteractivity}
            backgroundClasses={isInteractive ? "" : "bg-destructive"}
            iconClasses={
              isInteractive ? "" : "text-primary-foreground dark:text-primary"
            }
            testId="lock_unlock_dropdown"
          /> */}
          {/* <DropdownControlButton
            iconName={helperLineEnabled ? "FoldHorizontal" : "UnfoldHorizontal"}
            tooltipText={
              helperLineEnabled ? "Hide Helper Lines" : "Show Helper Lines"
            }
            onClick={onToggleHelperLines}
            backgroundClasses={cn(helperLineEnabled && "bg-muted")}
            iconClasses={cn(helperLineEnabled && "text-muted-foreground")}
            testId="helper_lines_dropdown"
          /> */}
        </DropdownMenuContent>
      </DropdownMenu>
      <span>
        <Separator orientation="vertical" />
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="group rounded flex items-center justify-center mr-1"
      >
        <IconComponent
          name="Circle-Help"
          aria-hidden="true"
          className="text-muted-foreground group-hover:text-primary !h-5 !w-5"
        />
      </Button>
    </Panel>
  );
};

export default CanvasControls;
