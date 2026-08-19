import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import ToggleShadComponent from "@/components/core/parameterRenderComponent/components/toggleShadComponent";
import { Button } from "@/components/ui/button";
import { ENABLE_INSPECTION_PANEL } from "@/customization/feature-flags";
import { useShortcutsStore } from "@/stores/shortcuts";
import { cn } from "@/utils/utils";
import ShortcutDisplay from "../shortcutDisplay";
import { ToolbarButton } from "./toolbar-button";

export interface ToolbarButtonRowProps {
  canEditCode: boolean;
  isCustomComponent: boolean;
  onCode: () => void;
  onToggleInspectionPanel: () => void;
  inspectionPanelVisible: boolean;
  hasToolMode: boolean;
  frozen: boolean;
  /** takeSnapshot + FreezeAllVertices, composed by the toolbar. */
  onFreeze: () => void;
  toolMode: boolean;
  /** takeSnapshot + toolMode dispatch, composed by the toolbar. */
  onToolMode: () => void;
}

/**
 * The always-visible row of toolbar buttons (edit code, parameters panel,
 * freeze / tool-mode toggle). Extracted verbatim from NodeToolbarComponent
 * (LE-1736 W30); reads shortcuts from the store for display.
 */
export function ToolbarButtonRow({
  canEditCode,
  isCustomComponent,
  onCode,
  onToggleInspectionPanel,
  inspectionPanelVisible,
  hasToolMode,
  frozen,
  onFreeze,
  toolMode,
  onToolMode,
}: ToolbarButtonRowProps): JSX.Element {
  const { t } = useTranslation();
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  return (
    <>
      {canEditCode && (
        <ToolbarButton
          className={isCustomComponent ? "animate-pulse-pink" : ""}
          icon="Code"
          label={t("nodeToolbar.code")}
          onClick={onCode}
          shortcut={shortcuts.find((s) =>
            s.name.toLowerCase().startsWith("code"),
          )}
          dataTestId="code-button-modal"
        />
      )}
      {/* Gated on the same flag the panel itself honors — without it the
          button would render and do nothing (setInspectionPanelVisible
          early-returns when the flag is off). */}
      {ENABLE_INSPECTION_PANEL && (
        <ToolbarButton
          icon="SlidersHorizontal"
          label={t("nodeToolbar.parameters")}
          onClick={onToggleInspectionPanel}
          shortcut={shortcuts.find((s) =>
            s.name.toLowerCase().startsWith("advanced"),
          )}
          isActive={inspectionPanelVisible}
          dataTestId="parameters-button"
        />
      )}
      {!hasToolMode && (
        <ToolbarButton
          icon="FreezeAll"
          label={t("nodeToolbar.freeze")}
          dataTestId="freeze-all-button-modal"
          onClick={onFreeze}
          shortcut={shortcuts.find((s) =>
            s.name.toLowerCase().startsWith("freeze"),
          )}
          className={cn(
            "node-toolbar-buttons",
            frozen && "text-accent-indigo-foreground",
          )}
        />
      )}
      {hasToolMode && (
        <ShadTooltip
          content={
            <ShortcutDisplay
              {...shortcuts.find(
                ({ name }) => name.toLowerCase() === "tool mode",
              )!}
            />
          }
          side="top"
          ariaDescribedBy={undefined}
        >
          <Button
            asChild
            className={cn(
              "node-toolbar-buttons h-[2rem]",
              toolMode && "text-primary",
            )}
            variant="ghost"
            size="node-toolbar"
            data-testid="tool-mode-button"
          >
            <div
              className="flex items-center gap-2"
              role="button"
              tabIndex={0}
              aria-pressed={toolMode}
              onClick={(event) => {
                event.preventDefault();
                onToolMode();
              }}
              // A plain div doesn't get the browser's native
              // button-activates-on-Enter/Space behavior — without this the
              // div is an announced-but-inert control from the keyboard.
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                onToolMode();
              }}
            >
              <IconComponent
                name="Hammer"
                className={cn(
                  "h-4 w-4 transition-all",
                  toolMode ? "text-primary" : "",
                )}
              />
              <span className="text-mmd font-medium">
                {t("nodeToolbar.toolMode")}
              </span>
              {/* This div is the real, keyboard-operable control (role="button"
                  above) and now carries its own aria-pressed. The nested
                  Switch is a visual echo of the same state, not a second
                  control — pulled out of tab order and hidden from the a11y
                  tree so it isn't a redundant, half-working focus stop. */}
              <div aria-hidden="true">
                <ToggleShadComponent
                  value={toolMode}
                  editNode={false}
                  handleOnNewValue={onToolMode}
                  disabled={false}
                  size="medium"
                  showToogle={false}
                  id="tool-mode-toggle"
                  tabIndex={-1}
                />
              </div>
            </div>
          </Button>
        </ShadTooltip>
      )}
    </>
  );
}
