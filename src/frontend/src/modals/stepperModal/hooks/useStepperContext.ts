import { createContext, useContext } from "react";
import type { StepperContextValue } from "../types";

export const StepperContext = createContext<StepperContextValue | null>(null);

export function useStepperContext() {
  const context = useContext(StepperContext);
  if (!context) {
    throw new Error("useStepperContext must be used within a StepperModal");
  }
  return context;
}
