import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/utils/utils";
import { switchCaseModalSize } from "../baseModal/helpers/switch-case-size";
import { HorizontalStepRail } from "./components/HorizontalStepRail";
import { ProgressIndicator } from "./components/ProgressIndicator";
import { SidePanel } from "./components/SidePanel";
import { StepRail } from "./components/StepRail";
import {
  DEFAULT_FULL_PAGE,
  DEFAULT_ICON,
  DEFAULT_SHOW_PROGRESS,
  DEFAULT_SIDE_PANEL_OPEN,
  DEFAULT_SIZE,
} from "./constants";
import { StepperContext } from "./hooks/useStepperContext";
import type { StepperModalProps } from "./types";

export function StepperModal({
  open,
  onOpenChange,
  currentStep,
  totalSteps,
  title,
  description,
  icon = DEFAULT_ICON,
  children,
  footer,
  className,
  contentClassName,
  size = DEFAULT_SIZE,
  showProgress = DEFAULT_SHOW_PROGRESS,
  height: customHeight,
  width: customWidth,
  sidePanel,
  sidePanelOpen = DEFAULT_SIDE_PANEL_OPEN,
  stepLabels,
  fullPage = DEFAULT_FULL_PAGE,
  onBack,
  backLabel,
  bgClassName,
}: StepperModalProps) {
  const { minWidth, height: sizeHeight } = switchCaseModalSize(size);
  const isNumericHeight = customHeight && /^\d+$/.test(customHeight);
  const heightClass = isNumericHeight ? undefined : customHeight || sizeHeight;
  const heightStyle = isNumericHeight
    ? { height: `${customHeight}px` }
    : undefined;

  const useRailLayout = !!stepLabels && stepLabels.length > 0;

  if (fullPage && open) {
    return (
      <StepperContext.Provider
        value={{ currentStep, totalSteps, title, description }}
      >
        <div
          className={cn(
            "fixed inset-0 z-50 flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-300",
            bgClassName || "bg-background",
          )}
        >
          {/* Full-page header */}
          <div className="flex flex-col gap-4 px-8 pt-[45px]">
            <div
              className={cn(
                "mx-auto flex w-full flex-col gap-4 ",
                customWidth || "max-w-2xl 3xl:container",
              )}
            >
              {onBack && (
                <button
                  type="button"
                  onClick={onBack}
                  className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <ForwardedIconComponent
                    name="ChevronLeft"
                    className="h-4 w-4"
                  />
                  {backLabel || "Back"}
                </button>
              )}
              <div className="flex flex-col gap-1">
                <h1 className="text-xl font-semibold">{title}</h1>
                {description && (
                  <p className="text-sm text-muted-foreground">{description}</p>
                )}
              </div>
              {stepLabels && stepLabels.length > 0 && (
                <div className="w-full pt-2">
                  <HorizontalStepRail
                    stepLabels={stepLabels}
                    currentStep={currentStep}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Full-page content */}
          <div className="flex flex-1 justify-center overflow-y-auto py-6 ">
            <div
              className={cn(
                "w-full rounded-xl border border-border p-6",
                customWidth || "max-w-2xl",
                contentClassName,
              )}
            >
              {children}
            </div>
          </div>

          {/* Full-page footer */}
          {footer && (
            <div className="flex items-center justify-center px-8 pb-10">
              <div className={cn("w-full", customWidth || "max-w-2xl")}>
                {footer}
              </div>
            </div>
          )}
        </div>
      </StepperContext.Provider>
    );
  }

  return (
    <StepperContext.Provider
      value={{ currentStep, totalSteps, title, description }}
    >
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          style={heightStyle}
          className={cn(
            "flex max-h-[85vh] gap-0 overflow-visible border bg-background p-0 shadow-lg transition-[height,width,border-radius,opacity] duration-300 ease-in-out",
            useRailLayout ? "flex-row" : "flex-col",
            customWidth ? `${customWidth} !max-w-none` : minWidth,
            heightClass,
            sidePanel && sidePanelOpen
              ? "rounded-l-xl rounded-r-none border-r-0"
              : "rounded-xl",
            className,
          )}
          closeButtonClassName="top-4 right-4"
        >
          {useRailLayout ? (
            <>
              {/* Accessibility: visually hidden but present for screen readers */}
              <DialogTitle className="sr-only">{title}</DialogTitle>
              {description && (
                <DialogDescription className="sr-only">
                  {description}
                </DialogDescription>
              )}

              <StepRail
                icon={icon}
                title={title}
                description={description}
                stepLabels={stepLabels}
                currentStep={currentStep}
              />

              <div className="flex min-w-0 flex-1 flex-col">
                <div className="flex-1 min-h-0 overflow-y-auto px-6 py-6 pr-14">
                  {children}
                </div>
                {footer && (
                  <div className="flex items-center border-t border-border px-6 py-4">
                    {footer}
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              {/* Legacy stacked layout */}
              <div className="flex flex-col gap-1 px-4 pt-4 pr-14">
                <div className="flex items-center justify-between">
                  <DialogTitle className="flex items-center gap-2 text-base font-semibold">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                      <ForwardedIconComponent name={icon} className="h-4 w-4" />
                    </div>
                    {title}
                  </DialogTitle>
                  <div
                    className={cn(
                      "transition-all duration-300 ease-in-out",
                      showProgress
                        ? "opacity-100 translate-x-0"
                        : "opacity-0 translate-x-4 pointer-events-none",
                    )}
                  >
                    <ProgressIndicator
                      currentStep={currentStep}
                      totalSteps={totalSteps}
                    />
                  </div>
                </div>
                {description && (
                  <DialogDescription className="text-sm text-muted-foreground">
                    {description}
                  </DialogDescription>
                )}
              </div>

              <div
                className={cn(
                  "flex-1 min-h-0 overflow-hidden mx-4 mb-4 rounded-lg px-5 py-4",
                  contentClassName,
                )}
              >
                {children}
              </div>

              {footer && (
                <div className="flex items-center px-4 pb-4">{footer}</div>
              )}
            </>
          )}

          {sidePanel && <SidePanel open={sidePanelOpen}>{sidePanel}</SidePanel>}
        </DialogContent>
      </Dialog>
    </StepperContext.Provider>
  );
}

// Re-exports for public API
export { StepperModalFooter } from "./components/StepperModalFooter";
export { useStepperContext } from "./hooks/useStepperContext";
export type {
  StepperContextValue,
  StepperModalFooterProps,
  StepperModalProps,
  StepperModalSize,
} from "./types";

export default StepperModal;
