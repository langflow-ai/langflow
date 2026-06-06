import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Panel, useStoreApi } from "@xyflow/react";
import { ArrowRight, X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import langflowAssistantIdleIcon from "@/assets/langflow_assistant_idle.svg";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  readAssistantDiscovered,
  writeAssistantDiscovered,
} from "@/components/core/assistantPanel/hooks/assistant-discovery-storage";
import { Button } from "@/components/ui/button";
import { ENABLE_INSPECTION_PANEL } from "@/customization/feature-flags";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import useFlowBuilderWelcomeStore from "@/stores/flowBuilderWelcomeStore";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import type { AllNodeType } from "@/types/flow";
import CanvasControlsDropdown from "./CanvasControlsDropdown";
import HelpDropdown from "./HelpDropdown";

// Delay before the "Try the new Langflow Assistant!" tooltip surfaces, in ms.
// Long enough that an active user mid-task isn't interrupted; short enough
// that a user who landed on the canvas and paused gets the hint.
const ONBOARDING_TOOLTIP_DELAY_MS = 10_000;

const CanvasControls = ({
  children,
  selectedNode,
  effectiveLocked,
}: {
  children?: ReactNode;
  selectedNode: AllNodeType | null;
  effectiveLocked?: boolean;
}) => {
  const { t } = useTranslation();
  const reactFlowStoreApi = useStoreApi();
  const isFlowLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );
  const setAssistantSidebarOpen = useAssistantManagerStore(
    (state) => state.setAssistantSidebarOpen,
  );
  const assistantSidebarOpen = useAssistantManagerStore(
    (state) => state.assistantSidebarOpen,
  );
  const inspectionPanelVisible = useFlowStore(
    (state) => state.inspectionPanelVisible,
  );
  // While the FlowBuilderWelcome overlay is open, suppress the onboarding
  // tooltip — it renders via Portal and would float over the welcome.
  const isWelcomeOpen = useFlowBuilderWelcomeStore((state) => state.isOpen);
  // Same reason as the welcome suppression: the playground sliding container
  // renders above the canvas, but the tooltip's Portal escapes that stacking
  // context and would float on top of the playground.
  const isPlaygroundOpen = usePlaygroundStore((state) => state.isOpen);
  const setInspectionPanelVisible = useFlowStore(
    (state) => state.setInspectionPanelVisible,
  );

  // Discovery state — once true, the "New" pill + onboarding tooltip never
  // surface again on this browser. Two paths flip it: opening the assistant
  // and clicking X on the tooltip. Both prove the user noticed the feature.
  const [discovered, setDiscovered] = useState<boolean>(() =>
    readAssistantDiscovered(),
  );
  // Tooltip surfaces only AFTER the idle delay below — gives the canvas time
  // to settle and avoids being the first thing the user sees on cold mount.
  const [tooltipVisible, setTooltipVisible] = useState(false);

  useEffect(() => {
    if (discovered) return;
    const timer = window.setTimeout(() => {
      setTooltipVisible(true);
    }, ONBOARDING_TOOLTIP_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [discovered]);

  const markDiscovered = useCallback(() => {
    setDiscovered(true);
    setTooltipVisible(false);
    writeAssistantDiscovered();
  }, []);

  const handleAssistantClick = () => {
    if (!discovered) markDiscovered();
    setAssistantSidebarOpen(!assistantSidebarOpen);
  };

  const handleDismissTooltip = useCallback(
    (e: React.MouseEvent) => {
      // The dismiss X lives inside the button container; stop the click from
      // bubbling to ``handleAssistantClick`` which would open the panel.
      e.stopPropagation();
      markDiscovered();
    },
    [markDiscovered],
  );

  const [isAddNoteActive, setIsAddNoteActive] = useState(false);

  const handleAddNote = useCallback(() => {
    window.dispatchEvent(new Event("lf:start-add-note"));
    setIsAddNoteActive(true);
  }, []);

  useEffect(() => {
    const onEnd = () => setIsAddNoteActive(false);
    window.addEventListener("lf:end-add-note", onEnd);
    return () => window.removeEventListener("lf:end-add-note", onEnd);
  }, []);

  const locked = effectiveLocked ?? isFlowLocked;

  // Single source of truth for the onboarding moment — both the popover
  // tooltip and the "New" pill key off this so they appear together.
  const onboardingActive =
    !discovered &&
    !assistantSidebarOpen &&
    !isWelcomeOpen &&
    !isPlaygroundOpen &&
    tooltipVisible;

  useEffect(() => {
    reactFlowStoreApi.setState({
      nodesDraggable: !locked,
      nodesConnectable: !locked,
      elementsSelectable: !locked,
    });
  }, [locked, reactFlowStoreApi]);

  return (
    <>
      <Panel
        data-testid="main_canvas_controls"
        className="react-flow__controls flex !flex-row items-center gap-1 !overflow-visible rounded-lg bg-background p-1 fill-foreground stroke-foreground text-primary [&>button]:border-0"
        position="bottom-center"
      >
        {/* Wrap the assistant button + "New" pill in a Radix Popover so the
            onboarding tooltip can render in a Portal on ``document.body``.
            Without the portal the tooltip is absolutely positioned inside the
            ReactFlow Panel and gets clipped or stacked under the workspace
            sidebar (z-index races, overflow contexts). The portal lifts it
            above every sibling surface. */}
        <PopoverPrimitive.Root open={onboardingActive} modal={false}>
          <PopoverPrimitive.Anchor asChild>
            <div className="group relative">
              {/* "New" discovery pill — surfaces ONLY on hover, hidden when
                  the panel is open (active state shouldn't carry the nudge).
                  The pill keeps appearing on hover indefinitely; only the
                  lateral tooltip respects the persisted ``discovered`` flag.
                  Uses the brand token from index.css. */}
              {!assistantSidebarOpen && (
                <span
                  data-testid="assistant-button-new-pill"
                  // Visibility logic: stays in lock-step with the onboarding
                  // tooltip — when ``onboardingActive`` is true the pill is
                  // pinned open; otherwise it falls back to the hover-only
                  // behavior so power users still see it as a hint without
                  // it being intrusive.
                  className={`absolute -top-4 -left-1 z-10 flex items-center gap-0.5 rounded bg-accent-assistant-brand px-1 py-0.5 text-[9px] font-medium leading-none text-white transition-all duration-200 ${
                    onboardingActive
                      ? "opacity-100 scale-100"
                      : "opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100"
                  }`}
                >
                  <ForwardedIconComponent
                    name="Sparkles"
                    className="h-2.5 w-2.5"
                  />
                  {t("assistant.newPill")}
                </span>
              )}
              <Button
                unstyled
                size="icon"
                data-testid="assistant-button"
                className="group/btn relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-md hover:bg-muted"
                onClick={handleAssistantClick}
              >
                {/* Idle state — uses the design-tuned
                    ``langflow_assistant_idle.svg`` (noise filter + brand tint
                    baked into the SVG). Hidden whenever the panel is open so
                    the button reads as "active" alongside the open panel. */}
                <img
                  src={langflowAssistantIdleIcon}
                  alt={t("assistant.title")}
                  className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-150 ${
                    assistantSidebarOpen ? "opacity-0" : "group-hover:opacity-0"
                  }`}
                />
                {/* Brand-lit icon — surfaces on hover AND while the panel is
                    open; both states share the same active brand identity. */}
                <img
                  src={langflowAssistantIcon}
                  alt=""
                  aria-hidden="true"
                  className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-150 ${
                    assistantSidebarOpen
                      ? "opacity-100"
                      : "opacity-0 group-hover:opacity-100"
                  }`}
                />
              </Button>
            </div>
          </PopoverPrimitive.Anchor>
          <PopoverPrimitive.Portal>
            <PopoverPrimitive.Content
              side="left"
              // Breathing room between the tooltip and the assistant button.
              // 4px reads as "touching"; 12px gives a clear visual separation
              // that matches the spacing density of the canvas controls bar.
              sideOffset={12}
              align="center"
              // Prevent Radix from grabbing focus when the tooltip opens —
              // the user is mid-task on the canvas; surprise focus shifts
              // break their flow.
              onOpenAutoFocus={(e) => e.preventDefault()}
              onCloseAutoFocus={(e) => e.preventDefault()}
              data-testid="assistant-onboarding-tooltip"
              // Canvas-level stacking: kept BELOW the z-50 modal/dialog/dropdown
              // layer so the onboarding tooltip never floats in front of an open
              // modal (e.g. "My Files"). The Portal still lifts it clear of the
              // ReactFlow Panel's overflow/clipping; only the z-index is capped.
              className="z-40 flex items-center gap-2 whitespace-nowrap rounded-md bg-muted px-2.5 py-1.5 text-sm font-medium text-foreground shadow-md"
            >
              <button
                type="button"
                data-testid="assistant-onboarding-dismiss"
                aria-label={t("assistant.dismissOnboardingTooltip")}
                className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted-foreground/10 hover:text-foreground"
                onClick={handleDismissTooltip}
              >
                <X className="h-3.5 w-3.5" />
              </button>
              <span>{t("assistant.tryAssistant")}</span>
              <button
                type="button"
                data-testid="assistant-onboarding-open"
                aria-label={t("assistant.openAssistant")}
                className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-foreground transition-colors hover:bg-muted-foreground/10"
                onClick={handleAssistantClick}
              >
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </PopoverPrimitive.Content>
          </PopoverPrimitive.Portal>
        </PopoverPrimitive.Root>
        <CanvasControlsDropdown selectedNode={selectedNode} />
        <Button
          unstyled
          size="icon"
          data-testid="canvas-add-note-button"
          className="group flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
          title={t("canvas.addStickyNote")}
          onClick={handleAddNote}
        >
          <ForwardedIconComponent
            name="sticky-note"
            className={`h-[18px] w-[18px] transition-colors ${
              isAddNoteActive
                ? "text-foreground"
                : "text-muted-foreground group-hover:text-foreground"
            }`}
          />
        </Button>
        <HelpDropdown />
        {children}
        {ENABLE_INSPECTION_PANEL && (
          <Button
            unstyled
            size="icon"
            data-testid="canvas_controls_toggle_inspector"
            aria-pressed={inspectionPanelVisible}
            className={`group flex h-8 w-8 items-center justify-center rounded-md ${
              inspectionPanelVisible
                ? "bg-muted text-foreground"
                : "hover:bg-muted"
            }`}
            title={
              !selectedNode
                ? t("canvas.selectNodeForInspector")
                : inspectionPanelVisible
                  ? t("canvas.hideInspectorPanel")
                  : t("canvas.showInspectorPanel")
            }
            onClick={() => setInspectionPanelVisible(!inspectionPanelVisible)}
          >
            <ForwardedIconComponent
              name="SlidersHorizontal"
              className={`!h-5 !w-5 ${
                inspectionPanelVisible
                  ? "text-foreground"
                  : "text-muted-foreground group-hover:text-foreground"
              }`}
            />
          </Button>
        )}
      </Panel>
    </>
  );
};

export default CanvasControls;
