import { createContext, type ReactNode, useContext } from 'react';
import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/utils/utils';
import { switchCaseModalSize } from '../baseModal/helpers/switch-case-size';

export type StepperModalSize =
  | 'x-small'
  | 'smaller'
  | 'smaller-h-full'
  | 'small'
  | 'small-h-full'
  | 'medium'
  | 'medium-tall'
  | 'medium-h-full'
  | 'large'
  | 'large-h-full'
  | 'x-large';

// Context for stepper state
interface StepperContextValue {
  currentStep: number;
  totalSteps: number;
  title: string;
  description?: string;
}

const StepperContext = createContext<StepperContextValue | null>(null);

// Progress indicator component
function ProgressIndicator({
  currentStep,
  totalSteps,
}: {
  currentStep: number;
  totalSteps: number;
}) {
  const progressPercentage = ((currentStep - 1) / (totalSteps - 1)) * 100;

  return (
    <div className="flex items-center gap-3">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${Math.max(progressPercentage, 10)}%` }}
        />
      </div>
      <span className="text-sm text-muted-foreground whitespace-nowrap">
        {currentStep}/{totalSteps} completed
      </span>
    </div>
  );
}

// Main StepperModal component
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
}

export function StepperModal({
  open,
  onOpenChange,
  currentStep,
  totalSteps,
  title,
  description,
  icon = 'Database',
  children,
  footer,
  className,
  contentClassName,
  size = 'small-h-full',
  showProgress = true,
}: StepperModalProps) {
  const { minWidth, height } = switchCaseModalSize(size);

  return (
    <StepperContext.Provider
      value={{ currentStep, totalSteps, title, description }}
    >
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className={cn(
            'flex max-h-[85vh] flex-col gap-0 overflow-hidden rounded-xl border bg-background p-0 shadow-lg px-2 pb-2',
            minWidth,
            height,
            className
          )}
          closeButtonClassName="top-7 right-4"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 pt-4 pr-14">
            <div className="flex flex-col gap-1">
              <DialogTitle className="flex items-center gap-2 text-base font-semibold">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                  <ForwardedIconComponent name={icon} className="h-4 w-4" />
                </div>
                {title}
              </DialogTitle>
              {description && (
                <DialogDescription className="text-sm text-muted-foreground">
                  {description}
                </DialogDescription>
              )}
            </div>
            <div
              className={cn(
                'transition-all duration-300 ease-in-out',
                showProgress
                  ? 'opacity-100 translate-x-0'
                  : 'opacity-0 translate-x-4 pointer-events-none'
              )}
            >
              <ProgressIndicator
                currentStep={currentStep}
                totalSteps={totalSteps}
              />
            </div>
          </div>

          {/* Content */}
          <div
            className={`flex-1 overflow-y-auto px-4 py-4 border border-border m-4 rounded-lg ${contentClassName}`}
          >
            {children}
          </div>

          {/* Footer */}
          {footer && (
            <div className="flex items-center px-4 pb-4">{footer}</div>
          )}
        </DialogContent>
      </Dialog>
    </StepperContext.Provider>
  );
}

// Footer component for convenience
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
}

export function StepperModalFooter({
  currentStep,
  totalSteps,
  onBack,
  onNext,
  onSubmit,
  nextDisabled = false,
  submitDisabled = false,
  isSubmitting = false,
  submitLabel = 'Create',
  nextLabel = 'Next Step',
  backLabel = 'Back',
  helpHref,
  onHelp,
  helpLabel = 'Need Help?',
}: StepperModalFooterProps) {
  const showHelp = helpHref || onHelp;

  return (
    <div className="flex w-full items-center justify-between pt-2">
      <div>
        {showHelp &&
          (helpHref ? (
            <Button
              variant="link"
              asChild
              className="px-2 text-muted-foreground"
            >
              <a
                href={helpHref}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                {helpLabel}
                <ForwardedIconComponent
                  name="ExternalLink"
                  className="ml-1 h-4 w-4"
                />
              </a>
            </Button>
          ) : (
            <Button variant="secondary" onClick={onHelp}>
              {helpLabel}
            </Button>
          ))}
      </div>
      <div className="flex items-center gap-3">
        {currentStep > 1 && onBack && (
          <Button variant="outline" onClick={onBack}>
            {backLabel}
          </Button>
        )}
        {currentStep < totalSteps ? (
          <Button onClick={onNext} disabled={nextDisabled}>
            {nextLabel}
          </Button>
        ) : (
          <Button onClick={onSubmit} disabled={submitDisabled || isSubmitting}>
            {isSubmitting && (
              <ForwardedIconComponent
                name="Loader2"
                className="mr-2 h-4 w-4 animate-spin"
              />
            )}
            {submitLabel}
          </Button>
        )}
      </div>
    </div>
  );
}

// Hook to access stepper context
export function useStepperContext() {
  const context = useContext(StepperContext);
  if (!context) {
    throw new Error('useStepperContext must be used within a StepperModal');
  }
  return context;
}

export default StepperModal;
