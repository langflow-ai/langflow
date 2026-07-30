import type { ReactNode } from "react";

export type StepperModalSize =
  | "x-small"
  | "smaller"
  | "smaller-h-full"
  | "small"
  | "small-h-full"
  | "medium"
  | "medium-tall"
  | "medium-h-full"
  | "large"
  | "large-h-full"
  | "x-large";

export interface StepperContextValue {
  currentStep: number;
  totalSteps: number;
  title: string;
  description?: string;
}

export interface StepperModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentStep: number;
  totalSteps: number;
  title: string;
  description?: string;
  icon?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
  size?: StepperModalSize;
  showProgress?: boolean;
  height?: string;
  width?: string;
  sidePanel?: ReactNode;
  sidePanelOpen?: boolean;
  /** Called when the dialog closes and focus would return to the trigger. */
  onCloseAutoFocus?: (event: Event) => void;
}

export interface StepperStepConfig {
  /** Stable step identity — named steps; `goTo` accepts it. */
  id: string;
  /** Optional label for step indicators. */
  label?: string;
  /**
   * Per-step validation gate: while false, `next()` is a no-op and
   * `canGoNext` is false. Defaults to true. The function form is evaluated on
   * every render (it feeds `canGoNext`), so it must be pure and side-effect-free.
   */
  canNext?: boolean | (() => boolean);
}

export interface UseStepperStateOptions {
  /**
   * Ordered step list, computed by the consumer. Conditional steps are
   * expressed by computing a different list (e.g. edit mode omits a step).
   */
  steps: readonly StepperStepConfig[];
  /** 1-based step the stepper starts at and `reset()` returns to. Default 1. */
  initialStep?: number;
  /**
   * 1-based floor `back()`/`goTo()` cannot go below. Independent from
   * initialStep: a stepper may open at step 2 and still allow going back
   * to step 1 (minStep 1), or forbid it (minStep 2). Default 1.
   */
  minStep?: number;
  /**
   * Consumer-owned busy flag (submitting/deploying/loading). While true,
   * all transitions are gated and `canGoNext`/`canGoBack` are false.
   */
  isBusy?: boolean;
  /** Called after a committed transition (from !== to), 1-based steps. */
  onStepChange?: (fromStep: number, toStep: number) => void;
}

export interface StepperState {
  /** 1-based current step, clamped to the step list. */
  currentStep: number;
  /** 0-based index into `steps`. */
  currentStepIndex: number;
  /** Id of the current step config ("" when the list is empty). */
  currentStepId: string;
  totalSteps: number;
  minStep: number;
  isFirstStep: boolean;
  isLastStep: boolean;
  canGoNext: boolean;
  canGoBack: boolean;
  isBusy: boolean;
  /** 0..100 progress, the indicators' `(current-1)/(total-1)` formula. */
  progressPercent: number;
  next: () => void;
  back: () => void;
  /** Jump to a step by id or 1-based number, clamped to [minStep, total]. */
  goTo: (stepIdOrNumber: string | number) => void;
  /** Return to `initialStep` (cancel + reopen fresh). Not busy-gated. */
  reset: () => void;
}

export interface StepperProviderProps extends UseStepperStateOptions {
  children: ReactNode;
}

export interface StepperModalFooterProps {
  currentStep: number;
  totalSteps: number;
  onBack?: () => void;
  onNext?: () => void;
  onSubmit?: () => void;
  nextDisabled?: boolean;
  submitDisabled?: boolean;
  isSubmitting?: boolean;
  submitLabel?: string;
  nextLabel?: string;
  backLabel?: string;
  helpHref?: string;
  onHelp?: () => void;
  helpLabel?: string;
  submitTestId?: string;
}
