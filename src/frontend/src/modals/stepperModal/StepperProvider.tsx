import { createContext, useContext } from "react";
import { useStepperState } from "./hooks/useStepperState";
import type { StepperProviderProps, StepperState } from "./types";

const StepperStateContext = createContext<StepperState | null>(null);

/**
 * Generic stepper provider over the headless {@link useStepperState} hook.
 * Wrap the stepper UI (shell, footer, step content) and read the transition
 * state anywhere below with {@link useStepper}. Shell-less flows can call
 * the hook directly instead.
 */
export function StepperProvider({
  children,
  ...options
}: StepperProviderProps) {
  const state = useStepperState(options);
  return (
    <StepperStateContext.Provider value={state}>
      {children}
    </StepperStateContext.Provider>
  );
}

export function useStepper(): StepperState {
  const context = useContext(StepperStateContext);
  if (!context) {
    throw new Error("useStepper must be used within a StepperProvider");
  }
  return context;
}
