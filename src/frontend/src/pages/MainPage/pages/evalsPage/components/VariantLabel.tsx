import { useTranslation } from "react-i18next";
import type { ModelOverride } from "@/controllers/API/queries/evals/types";
import { variantModels, variantProviders } from "../utils/comparison";
import VariantMarker from "./VariantMarker";

/** A model version as text: its number, the models it swaps in (or the flow's own), and their providers. */
export function variantName(
  overrides: readonly ModelOverride[],
  t: (key: string) => string,
): string {
  const models = variantModels(overrides);
  return models.length > 0 ? models.join(" + ") : t("evals.compare.flowModels");
}

export default function VariantLabel({
  index,
  overrides,
  detail = true,
}: {
  index: number;
  overrides: readonly ModelOverride[];
  detail?: boolean;
}) {
  const { t } = useTranslation();
  const providers = variantProviders(overrides);
  return (
    <span className="flex min-w-0 items-center gap-2">
      <VariantMarker index={index} />
      <span className="flex min-w-0 flex-col">
        <span className="truncate">{variantName(overrides, t)}</span>
        {detail && (
          <span className="truncate text-xs text-muted-foreground">
            {providers.length > 0
              ? providers.join(" + ")
              : t("evals.compare.flowModelsHint")}
          </span>
        )}
      </span>
    </span>
  );
}
