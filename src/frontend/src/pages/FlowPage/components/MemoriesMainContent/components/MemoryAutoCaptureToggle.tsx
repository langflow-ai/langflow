import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { NextIsActive } from "../hooks/useAutoCaptureDebouncedToggle";

export interface MemoryAutoCaptureToggleProps {
  /** Whether auto-capture is currently active (post-debounce, draft-aware). */
  isActive: boolean;
  /** Invoked with an updater on click; the parent owns debouncing/state. */
  onToggle: (next: NextIsActive) => void;
  /** Optional override for the button data-testid. */
  testId?: string;
}

/**
 * Auto-capture toggle button for the Memory details header.
 *
 * Renders the toggle icon, label, and a status pill (Badge primitive)
 * that signals the current ON/OFF state. The whole control is a single
 * accessible button: ``aria-pressed`` mirrors the state and the
 * ``aria-label`` switches between the enable/disable phrasing so screen
 * readers announce the action being taken, not just the label.
 *
 * Presentational by design — debouncing and toast plumbing live in the
 * parent hook (``useAutoCaptureDebouncedToggle``) so this component
 * stays trivially testable and reusable anywhere a single memory's
 * auto-capture state needs a toggle.
 */
export function MemoryAutoCaptureToggle({
  isActive,
  onToggle,
  testId = "memory-auto-capture-toggle",
}: MemoryAutoCaptureToggleProps) {
  const { t } = useTranslation();

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => onToggle((prev) => !prev)}
      aria-pressed={isActive}
      aria-label={
        isActive
          ? t("memories.autoCapture.ariaDisable")
          : t("memories.autoCapture.ariaEnable")
      }
      className="gap-2"
      data-testid={testId}
    >
      <IconComponent
        name={isActive ? "ToggleRight" : "ToggleLeft"}
        className={
          isActive
            ? "h-4 w-4 text-accent-emerald-foreground"
            : "h-4 w-4 text-muted-foreground"
        }
      />
      <span>{t("memories.autoCapture.label")}</span>
      <Badge
        variant={isActive ? "successStatic" : "secondaryStatic"}
        size="sm"
        className="uppercase tracking-wide"
        data-testid={`${testId}-state`}
      >
        {isActive
          ? t("memories.autoCapture.stateOn")
          : t("memories.autoCapture.stateOff")}
      </Badge>
    </Button>
  );
}

export default MemoryAutoCaptureToggle;
