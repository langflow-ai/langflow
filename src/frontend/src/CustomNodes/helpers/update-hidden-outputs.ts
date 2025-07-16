import type { OutputFieldType } from "@/types/api";

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
    });
    return updatedOutputs;
  }

  return outputs;
};
