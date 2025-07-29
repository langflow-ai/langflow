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
        <div
          className={cn(
            "rounded p-2.5 flex items-center justify-center",
            backgroundClasses,
          )}
        >
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

// Component for dropdown control buttons with keyboard shortcuts
const DropdownControlButton = ({
  tooltipText,
  onClick,
  disabled,
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
      title={tooltipText}
    >
      <div className="flex flex-row items-center justify-between w-full h-full">
        <span className="text-muted-foreground text-sm mr-2">{name}</span>
        <div className="flex flex-row items-center justify-center gap-1 text-sm text-placeholder-foreground">
          <span className="mr-1">{getModifierKey()}</span>
          <span>{shortcut}</span>
        </div>
      </div>
    </Button>
  );
};

// Helper function to get OS-specific modifier key
const getModifierKey = (): string => {
  const os = getOS();
  return os === "macos" ? "⌘" : "Ctrl";
};

// Helper function to format zoom percentage
const formatZoomPercentage = (zoom: number): string => {
  return `${Math.round(zoom * 100)}%`;
};

// Keyboard shortcuts configuration
const SHORTCUTS = {
  ZOOM_IN: { key: "+", code: "Equal" },
  ZOOM_OUT: { key: "-", code: "Minus" },
  FIT_VIEW: { key: "1", code: "Digit1" },
  RESET_ZOOM: { key: "0", code: "Digit0" },
} as const;

const selector = (s: ReactFlowState) => ({
  isInteractive: s.nodesDraggable || s.nodesConnectable || s.elementsSelectable,
  minZoomReached: s.transform[2] <= s.minZoom,
  maxZoomReached: s.transform[2] >= s.maxZoom,
  zoom: s.transform[2],
});

const CanvasControls = ({ children }) => {
  const store = useStoreApi();
  const { fitView, zoomIn, zoomOut, zoomTo } = useReactFlow();
  const { isInteractive, minZoomReached, maxZoomReached, zoom } = useStore(
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

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isModifierPressed = event.metaKey || event.ctrlKey;

      if (!isModifierPressed) return;

      switch (event.code) {
        case SHORTCUTS.ZOOM_IN.code:
          event.preventDefault();
          if (!maxZoomReached) {
            zoomIn();
          }
          break;
        case SHORTCUTS.ZOOM_OUT.code:
          event.preventDefault();
          // If we're at or near minimum zoom, reset to 100% instead
          if (minZoomReached || zoom <= 0.6) {
            zoomTo(1);
          } else {
            zoomOut();
          }
          break;
        case SHORTCUTS.FIT_VIEW.code:
          event.preventDefault();
          fitView();
          break;
        case SHORTCUTS.RESET_ZOOM.code:
          event.preventDefault();
          zoomTo(1);
          break;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [zoomIn, zoomOut, fitView, zoomTo, maxZoomReached, minZoomReached]);

  useEffect(() => {
    store.setState({
      nodesDraggable: !isLocked,
      nodesConnectable: !isLocked,
      elementsSelectable: !isLocked,
    });
  }, [isLocked, store]);

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

  const handleResetZoom = useCallback(() => {
    zoomTo(1);
    setDropdownOpen(false);
  }, [zoomTo]);

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

      {/* Canvas Controls Dropdown */}
      <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            data-testid="canvas_controls_dropdown"
            className="group rounded !p-0"
            title="Canvas Controls"
          >
            <ShadTooltip content="Canvas Controls" side="top" align="end">
              <div className="rounded py-2.5 px-1 flex items-center justify-center">
                <div className="text-sm text-primary pr-2">
                  {formatZoomPercentage(zoom)}
                </div>
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
            tooltipText="Zoom In"
            onClick={handleZoomIn}
            disabled={maxZoomReached}
            testId="zoom_in_dropdown"
            name="Zoom In"
            shortcut={SHORTCUTS.ZOOM_IN.key}
          />
          <DropdownControlButton
            tooltipText="Zoom Out"
            onClick={handleZoomOut}
            disabled={minZoomReached}
            testId="zoom_out_dropdown"
            name="Zoom Out"
            shortcut={SHORTCUTS.ZOOM_OUT.key}
          />
          <Separator />
          <DropdownControlButton
            tooltipText="Reset zoom to 100%"
            onClick={handleResetZoom}
            testId="reset_zoom_dropdown"
            name="Zoom To 100%"
            shortcut={SHORTCUTS.RESET_ZOOM.key}
          />
          <DropdownControlButton
            tooltipText="Fit view to show all nodes"
            onClick={handleFitView}
            testId="fit_view_dropdown"
            name="Zoom To Fit"
            shortcut={SHORTCUTS.FIT_VIEW.key}
          />
        </DropdownMenuContent>
      </DropdownMenu>

      <span>
        <Separator orientation="vertical" />
      </span>

      {/* Help Button */}
      <Button
        variant="ghost"
        size="icon"
        className="group rounded flex items-center justify-center mr-1"
        title="Help"
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
