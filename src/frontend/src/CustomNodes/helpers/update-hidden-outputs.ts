import type { OutputFieldType } from "@/types/api";
import { typeIsCompatibleWith } from "@/utils/reactflowUtils";

export const updateHiddenOutputs = (
  outputs: OutputFieldType[],
  updatedOutputs: OutputFieldType[],
) => {
  if (outputs && updatedOutputs) {
    outputs.forEach((output) => {
      const indexOutput = updatedOutputs?.findIndex(
        (o) => o.name === output.name,
      );
      if (indexOutput === -1 || indexOutput === undefined) return;
      updatedOutputs![indexOutput].hidden = output.hidden;
      // Options (the inspection view's filter) are only ever set by the user.
      if (output.options) {
        updatedOutputs![indexOutput].options = output.options;
      }
      // Edges carry the selected type, so keep the saved pick (or the only type of an output saved
      // without one) while the output offers it, exactly or else in the output's own spelling of a
      // historical name (Data/JSON, DataFrame/Table).
      const picked =
        typeof output.selected === "string" || output.types?.length !== 1
          ? output.selected
          : output.types[0];
      if (typeof picked === "string") {
        const types = updatedOutputs![indexOutput].types ?? [];
        const selected = types.includes(picked)
          ? picked
          : types.find((type) => typeIsCompatibleWith(picked, [type]));
        if (selected) {
          updatedOutputs![indexOutput].selected = selected;
        }
      }
    });
    return updatedOutputs;
  }

  return outputs;
};
