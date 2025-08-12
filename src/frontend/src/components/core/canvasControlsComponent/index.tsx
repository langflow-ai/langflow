import { Separator } from "@/components/ui/separator";
import useFlowStore from "@/stores/flowStore";
import {
  Panel,
  useReactFlow,
  useStore,
  useStoreApi,
  type ReactFlowState,
} from "@xyflow/react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useShallow } from "zustand/react/shallow";
import { shallow } from "zustand/shallow";
import { CanvasControlsDropdown, HelpDropdown } from "./dropdowns";

const KEYBOARD_SHORTCUTS = {
  ZOOM_IN: { key: "+", code: "Equal" },
  ZOOM_OUT: { key: "-", code: "Minus" },
  FIT_VIEW: { key: "1", code: "Digit1" },
  RESET_ZOOM: { key: "0", code: "Digit0" },
} as const;

const reactFlowSelector = (s: ReactFlowState) => ({
  isInteractive: s.nodesDraggable || s.nodesConnectable || s.elementsSelectable,
  minZoomReached: s.transform[2] <= s.minZoom,
  maxZoomReached: s.transform[2] >= s.maxZoom,
  zoom: s.transform[2],
});

const CanvasControls = ({ children }: { children?: ReactNode }) => {
  const reactFlowStoreApi = useStoreApi();
  const { fitView, zoomIn, zoomOut, zoomTo } = useReactFlow();
  const { minZoomReached, maxZoomReached, zoom } = useStore(
    reactFlowSelector,
    shallow,
  );
  const [isControlsMenuOpen, setIsControlsMenuOpen] = useState(false);
  const [isHelpMenuOpen, setIsHelpMenuOpen] = useState(false);
  const isFlowLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );


  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isModifierPressed = event.metaKey || event.ctrlKey;

      if (!isModifierPressed) return;

      switch (event.code) {
        case KEYBOARD_SHORTCUTS.ZOOM_IN.code:
          event.preventDefault();
          if (!maxZoomReached) {
            zoomIn();
          }
          break;
        case KEYBOARD_SHORTCUTS.ZOOM_OUT.code:
          event.preventDefault();
          if (minZoomReached || zoom <= 0.6) {
            zoomTo(1);
          } else {
            zoomOut();
          }
          break;
        case KEYBOARD_SHORTCUTS.FIT_VIEW.code:
          event.preventDefault();
          fitView();
          break;
        case KEYBOARD_SHORTCUTS.RESET_ZOOM.code:
          event.preventDefault();
          zoomTo(1);
          break;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [zoomIn, zoomOut, fitView, zoomTo, maxZoomReached, minZoomReached]);

  useEffect(() => {
    reactFlowStoreApi.setState({
      nodesDraggable: !isFlowLocked,
      nodesConnectable: !isFlowLocked,
      elementsSelectable: !isFlowLocked,
    });
  }, [isFlowLocked, reactFlowStoreApi]);

  const handleZoomIn = useCallback(() => {
    zoomIn();
    setIsControlsMenuOpen(false);
  }, [zoomIn]);

  const handleZoomOut = useCallback(() => {
    zoomOut();
    setIsControlsMenuOpen(false);
  }, [zoomOut]);

  const handleFitView = useCallback(() => {
    fitView();
    setIsControlsMenuOpen(false);
  }, [fitView]);

  const handleResetZoom = useCallback(() => {
    zoomTo(1);
    setIsControlsMenuOpen(false);
  }, [zoomTo]);

  return (
    <Panel
      data-testid="main_canvas_controls"
      className="react-flow__controls !left-auto !m-2 flex !flex-row rounded-md border border-border bg-background fill-foreground stroke-foreground text-primary [&>button]:border-0"
      position="bottom-right"
    >
      {children}
      {children && (
        <span>
          <Separator orientation="vertical" />
        </span>
      )}

      <CanvasControlsDropdown
        zoom={zoom}
        minZoomReached={minZoomReached}
        maxZoomReached={maxZoomReached}
        isOpen={isControlsMenuOpen}
        onOpenChange={setIsControlsMenuOpen}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onResetZoom={handleResetZoom}
        onFitView={handleFitView}
        shortcuts={KEYBOARD_SHORTCUTS}
      />
      <span>
        <Separator orientation="vertical" />
      </span>
      <HelpDropdown
        isOpen={isHelpMenuOpen}
        onOpenChange={setIsHelpMenuOpen}
        onSelectAction={() => setIsHelpMenuOpen(false)}
      />
    </Panel>
  );
};

export default CanvasControls;
