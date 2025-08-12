import IconComponent, { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { DATASTAX_DOCS_URL, DESKTOP_URL, DOCS_URL } from "@/constants/constants";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { cn, getOS } from "@/utils/utils";
import React from "react";
import { useNavigate } from "react-router-dom";

type DropdownControlButtonProps = {
  tooltipText?: string;
  onClick?: () => void;
  disabled?: boolean;
  testId?: string;
  label?: string;
  shortcut?: string;
  iconName?: string;
};

const getModifierKey = (): string => {
  const os = getOS();
  return os === "macos" ? "⌘" : "Ctrl";
};

const DropdownControlButton: React.FC<DropdownControlButtonProps> = ({
  tooltipText,
  onClick = () => {},
  disabled,
  testId,
  label = "",
  shortcut = "",
  iconName,
}) => (
  <Button
    data-testid={testId}
    className={cn(
      "group flex items-center justify-center !py-1.5 !px-2 hover:bg-accent h-full rounded-none",
      disabled && "cursor-not-allowed opacity-50",
    )}
    onClick={onClick}
    variant="ghost"
    disabled={disabled}
    title={tooltipText || ""}
  >
    {iconName && <ForwardedIconComponent name={iconName} className="text-muted-foreground group-hover:text-primary" />}
    <div className="flex flex-row items-center justify-between w-full h-full">
      <span className="text-muted-foreground text-sm mr-2 group-hover:text-primary">{label}</span>
      <div className="flex flex-row items-center justify-center gap-1 text-sm text-placeholder-foreground">
        {shortcut && (
          <>
            <span className="mr-1">{getModifierKey()}</span>
            <span>{shortcut}</span>
          </>
        )}
      </div>
    </div>
  </Button>
);

const formatZoomPercentage = (zoom: number): string =>
  `${Math.round(zoom * 100)}%`;

export type CanvasControlsDropdownProps = {
  zoom: number;
  minZoomReached: boolean;
  maxZoomReached: boolean;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetZoom: () => void;
  onFitView: () => void;
  shortcuts: {
    ZOOM_IN: { key: string };
    ZOOM_OUT: { key: string };
    RESET_ZOOM: { key: string };
    FIT_VIEW: { key: string };
  };
};

export const CanvasControlsDropdown: React.FC<CanvasControlsDropdownProps> = ({
  zoom,
  minZoomReached,
  maxZoomReached,
  isOpen,
  onOpenChange,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  onFitView,
  shortcuts,
}) => (
  <DropdownMenu open={isOpen} onOpenChange={onOpenChange}>
    <DropdownMenuTrigger asChild>
      <Button
        variant="ghost"
        data-testid="canvas_controls_dropdown"
        className="group rounded-none px-2 py-2 hover:bg-muted"
        unstyled
        title="Canvas Controls"
      >
          <div className="flex items-center justify-center ">
            <div className="text-sm text-primary pr-1">
              {formatZoomPercentage(zoom)}
            </div>
            <IconComponent
              name={isOpen ? "ChevronDown" : "ChevronUp"}
              aria-hidden="true"
              className="text-primary group-hover:text-primary !h-5 !w-5"
            />
          </div>
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent
      side="top"
      align="end"
      className="flex flex-col w-full"
    >
      <DropdownControlButton
        tooltipText="Zoom In"
        onClick={onZoomIn}
        disabled={maxZoomReached}
        testId="zoom_in_dropdown"
        label="Zoom In"
        shortcut={shortcuts.ZOOM_IN.key}
      />
      <DropdownControlButton
        tooltipText="Zoom Out"
        onClick={onZoomOut}
        disabled={minZoomReached}
        testId="zoom_out_dropdown"
        label="Zoom Out"
        shortcut={shortcuts.ZOOM_OUT.key}
      />
      <Separator />
      <DropdownControlButton
        tooltipText="Reset zoom to 100%"
        onClick={onResetZoom}
        testId="reset_zoom_dropdown"
        label="Zoom To 100%"
        shortcut={shortcuts.RESET_ZOOM.key}
      />
      <DropdownControlButton
        tooltipText="Fit view to show all nodes"
        onClick={onFitView}
        testId="fit_view_dropdown"
        label="Zoom To Fit"
        shortcut={shortcuts.FIT_VIEW.key}
      />
    </DropdownMenuContent>
  </DropdownMenu>
);

export type HelpDropdownProps = {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectAction?: (action: "mock1" | "mock2" | "mock3") => void;
};

export const HelpDropdown: React.FC<HelpDropdownProps> = ({
  isOpen,
  onOpenChange,
  onSelectAction,
}) => {
  const navigate = useNavigate();
  
  return (
  <DropdownMenu open={isOpen} onOpenChange={onOpenChange}>
    <DropdownMenuTrigger asChild>
      <Button
        variant="ghost"
        size="icon"
        className="group flex items-center justify-center px-2 rounded-none"
        title="Help"
     
      >
        <IconComponent
          name="Circle-Help"
          aria-hidden="true"
          className="text-muted-foreground group-hover:text-primary !h-5 !w-5"
        />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent
      side="top"
      align="end"
      className="flex flex-col w-full"
    >
      <DropdownControlButton
        iconName="book-open"
        testId="canvas_controls_dropdown_docs"
        label="Docs"
        onClick={() => {
          window.open(ENABLE_DATASTAX_LANGFLOW ? DATASTAX_DOCS_URL : DOCS_URL, "_blank");
        }}
      />
      <DropdownControlButton
        iconName="keyboard"
        testId="canvas_controls_dropdown_shortcuts"
        label="Shortcuts"
        onClick={() => {
          navigate("/settings/shortcuts");
        }}
      />
      {/* <DropdownControlButton
        iconName="bug"
        testId="canvas_controls_dropdown_report_a_bug"
        label="Report a bug"
      /> */}
      <Separator />
      <DropdownControlButton
        iconName="download"
        testId="canvas_controls_dropdown_get_langflow_desktop"
        label="Get Langflow Desktop"
        onClick={() => {
          window.open(DESKTOP_URL, "_blank");
        }}
      />
       {/* <DropdownControlButton
        iconName="cog"
        testId="canvas_controls_dropdown_enable_smart_guides"
        label="Enable smart guides"
        
      /> */}
    </DropdownMenuContent>
  </DropdownMenu>
);
};
