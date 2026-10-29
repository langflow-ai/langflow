import type {
  FlowModelPicker,
  ModelOverride,
  ModelSelection,
} from "@/controllers/API/queries/evals/types";

export type ChosenModels = Readonly<Record<string, ModelSelection>>;

export function pickerKey(picker: Pick<FlowModelPicker, "node_id" | "field">) {
  return `${picker.node_id}::${picker.field}`;
}

export function sameModel(left?: ModelSelection, right?: ModelSelection) {
  return (
    left?.[0]?.name === right?.[0]?.name &&
    left?.[0]?.provider === right?.[0]?.provider
  );
}

/** Only the pickers whose chosen model differs from the flow's: an unchanged one runs as saved. */
export function buildModelOverrides(
  pickers: readonly FlowModelPicker[],
  chosen: ChosenModels,
): ModelOverride[] {
  return pickers.flatMap((picker) => {
    const value = chosen[pickerKey(picker)];
    if (!value?.[0] || sameModel(value, picker.value)) return [];
    const { name, provider, icon, metadata } = value[0];
    return [
      {
        node_id: picker.node_id,
        field: picker.field,
        value: [{ name, provider, icon, metadata }],
      },
    ];
  });
}
