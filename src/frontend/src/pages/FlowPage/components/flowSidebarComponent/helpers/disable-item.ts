import { evaluatePlacement } from "@/utils/componentConstraints";

/**
 * Whether a sidebar item should be disabled because the component cannot be
 * added given the component types already present in the flow. Delegates to the
 * shared constraint engine so the policy lives in one place.
 */
export const disableItem = (
  candidate: string | readonly string[],
  presentTypes: ReadonlySet<string>,
): boolean => evaluatePlacement(candidate, presentTypes) !== null;
