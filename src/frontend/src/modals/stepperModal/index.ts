// Public surface of the stepper module. StepperModal.tsx already re-exports the
// headless hooks, provider and types (its "Re-exports for public API" block);
// this index makes that surface reachable as `@/modals/stepperModal` so headless
// consumers don't import from a file named after the modal component.

export * from "./StepperModal";
export { default } from "./StepperModal";
