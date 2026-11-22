import { useTranslation } from "react-i18next";
import type { DatasetItem } from "@/controllers/API/queries/evals/types";

/** The first rows of the chosen dataset, so the user sees what each run will be asked. */
export default function DatasetPreview({
  items,
  total,
}: {
  items: DatasetItem[];
  total: number;
}) {
  const { t } = useTranslation();
  if (items.length === 0) return null;
  const more = total - items.length;
  return (
    <section
      aria-labelledby="dataset-preview-title"
      className="flex flex-col gap-2"
      data-testid="evaluate-dataset-preview"
    >
      <h4 id="dataset-preview-title" className="text-sm font-medium">
        {t("evals.evaluate.previewTitle")}
      </h4>
      <ol className="divide-y rounded-lg border">
        {items.map((item) => (
          <li key={item.id} className="flex flex-col gap-0.5 px-3 py-2 text-sm">
            <span className="truncate">{item.input}</span>
            <span className="truncate text-xs text-muted-foreground">
              {item.expected_output ?? t("evals.evaluate.previewNoExpected")}
            </span>
          </li>
        ))}
      </ol>
      {more > 0 && (
        <span className="text-xs text-muted-foreground">
          {t("evals.evaluate.previewMore", { count: more })}
        </span>
      )}
    </section>
  );
}
