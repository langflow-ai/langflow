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
